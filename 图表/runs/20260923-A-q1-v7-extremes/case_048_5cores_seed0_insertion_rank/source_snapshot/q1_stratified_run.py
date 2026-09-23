"""Execute a pre-frozen stratified protocol with explicit timeout censoring."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time
from q1_io import sha, write_json
from q1_ablation_report import collect, compare


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    code = Path(__file__).parent
    for name, expected in profile['code_sha256'].items():
        if sha((code/name).read_bytes()) != expected:
            raise ValueError('Frozen source mismatch: '+name)
    protocol = profile['evaluation_protocol']
    args.output.mkdir(parents=True,exist_ok=False)
    state = {'profile_sha256':sha(args.profile.read_bytes()),'protocol':protocol,
             'finished':False,'all_runs_completed':False,'runs':[]}
    write_json(args.output/'batch.json',state)
    jobs = [(s['case'],c,seed,config) for s in profile['selection'] for c in protocol['cores']
            for seed in protocol['seeds'] for config in protocol['configs']]

    def run(job):
        case, cores, seed, config = job
        name = f'{case}_{cores}cores_seed{seed}_{config}'
        command = [sys.executable,str(code/'q1_ablation.py'),'--cases',case,'--cores',str(cores),
                   '--seeds',str(seed),'--configs',config,'--evaluations',str(protocol['candidate_budget']),
                   '--output',str(args.output/name)]
        started = time.perf_counter()
        row = {'case':case,'cores':cores,'seed':seed,'config':config,'directory':name,'command':command}
        with (args.output/(name+'.log')).open('wb') as log:
            try:
                completed = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,
                                           timeout=protocol['per_run_timeout_seconds'])
                row['status'] = 'complete' if completed.returncode == 0 else 'failed'
                row['exit_code'] = completed.returncode
            except subprocess.TimeoutExpired:
                row['status'] = 'timeout'
        row['wall_seconds'] = time.perf_counter()-started
        if row['status'] == 'complete':
            verified = collect(args.output/name)
            row['result'] = verified['runs'][0]
        return row

    with ThreadPoolExecutor(max_workers=protocol['max_workers']) as pool:
        futures = [pool.submit(run,j) for j in jobs]
        for future in as_completed(futures):
            row = future.result()
            state['runs'].append(row)
            write_json(args.output/'batch.json',state)
            print(len(state['runs']),len(jobs),row['directory'],row['status'],flush=True)
    state['finished'] = True
    state['all_runs_completed'] = all(r['status']=='complete' for r in state['runs'])
    write_json(args.output/'batch.json',state)
    paired, excluded = [], []
    for case, cores, seed in sorted({j[:3] for j in jobs}):
        group = [r for r in state['runs'] if (r['case'],r['cores'],r['seed'])==(case,cores,seed)]
        if all(r['status']=='complete' for r in group):
            paired.extend(r['result'] for r in group)
        else:
            excluded.append({'case':case,'cores':cores,'seed':seed,'statuses':{r['config']:r['status'] for r in group}})
    comparison = compare(paired,*protocol['configs']) if paired else None
    write_json(args.output/'comparison.json',{'comparison':comparison,'excluded_pairs':excluded,
              'protocol_sha256':state['profile_sha256'],'note':'Complete pairs only; timeouts are not scores and may bias the surviving sample.'})
    print(json.dumps({'complete_runs':sum(r['status']=='complete' for r in state['runs']),
                      'total_runs':len(jobs),'paired_cases':len(paired)//2,'excluded_pairs':len(excluded)},ensure_ascii=True))


if __name__=='__main__':
    main()
