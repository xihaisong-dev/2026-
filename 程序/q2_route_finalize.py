"""Index audit and completed structural pilot without changing prior evidence."""
import json,subprocess
from q1_io import ROOT,sha,write_json
from q2_route_campaign import OUT


def main():
    s=json.loads((OUT/'summary.json').read_text(encoding='utf-8'));ev=ROOT/'审查/证据/20260924-A-q2-compliance-r04-v2'
    audit=json.loads((ev/'audit.json').read_text(encoding='utf-8'));gate=s['confirmation']['comparisons'][1]['gate']
    sources=[ROOT/'程序'/name for name in ['q2_requirements_audit.py','q2_structural_route.py','q2_route_campaign.py','q2_route_finalize.py']]+[ROOT/'程序/tests/test_q2_structural_route.py']
    manifest=dict(status='pilot_complete',entry='程序/q2_route_campaign.py',files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p.read_bytes()),lines=len(p.read_text(encoding='utf-8').splitlines())) for p in sources])
    write_json(ev/'source_manifest.json',manifest)
    assert not subprocess.check_output(['git','diff','--name-only','HEAD','--','程序/q1_*.py','图表/runs/20260924-A-q1-delivery-r02'],cwd=ROOT,text=True).strip()
    decision=dict(hard_constraints_audit='PASS_ON_AUDITED_EVIDENCE',full_deliverables='NOT_COMPLETE',route_confirmation_gate=gate,
                  full100=False,default_changed=False,q1_unchanged=True,audit=s['audit'],tests_passed=14,
                  audit_report='审查/问题二建模解算要求审核_r04.md',experiment_report='审查/问题二结构准入对照_r04.md',
                  sources=manifest['files'],audit_evidence_sha256=sha((ev/'audit.json').read_bytes()))
    write_json(OUT/'decision.json',decision)
    for rel,item in [('程序/code_manifest.json',manifest),('图表/全部结果.json',decision)]:
        p=ROOT/rel;value=json.loads(p.read_text(encoding='utf-8'));assert 'q2_compliance_route_r04' not in value;value['q2_compliance_route_r04']=item;write_json(p,value)
    with (ROOT/'计算结果.md').open('a',encoding='utf-8') as f:
        f.write('\n\n## 问题二r04：要求审核与结构准入\n\n已审计176份历史结果，涉及11图40个多核配置；硬约束未发现违规，全量交付仍未完成。补导出24份标准名方案，六份真实全局驻留检查通过，两份官方CLI完整结果一致。首次CLI日志编码失败保留，3次额外CLI调用不混入算法预算。14项测试通过。\n\n')
        for phase in ['development','confirmation']:
            x=s[phase]['comparisons'][1];f.write(f"- {phase}结构准入相对legacy：{x['outcomes']}，几何平均提速比变化{(x['geomean_ratio']-1)*100:+.6f}%，条件={x['gate']}。\n")
        f.write('\n新增72份B完整最终回放一致，保护前6机会逐项核对，普通J预算不变。报告见审查/问题二建模解算要求审核_r04.md和审查/问题二结构准入对照_r04.md；全量要求与局限未隐去，Q1未改。\n')
    with (ROOT/'程序/README.md').open('a',encoding='utf-8') as f:
        f.write('\n\n### Q2 r04 审计与结构准入\n\n`q2_requirements_audit.py`只读核查历史方案并另存标准名样本导出；当前OUT-v2已存在，复现须新目录。`q2_route_campaign.py freeze`冻结，`run --phase development --case 12`等运行，`report`汇总；`q2_route_finalize.py`登记证据。每组12机会，路由仅可替换第7/8机会，J仍普通4次。所有输出禁止覆盖，当前默认q2_submit未改。\n')
    with (ROOT/'协作/AI使用记录.md').open('a',encoding='utf-8') as f:
        f.write('\n| 2026-09-24 | Codex | 问题二硬约束核查、标准名导出、结构准入实验 | 原题、官方代码、176份历史结果与预冻结6图 | 六份实际驻留、两份CLI、14项测试、新72份回放与机会保护核对；未声称完成全量交付 | 待指定 |\n')
    print(json.dumps(decision,ensure_ascii=False))


if __name__=='__main__':main()
