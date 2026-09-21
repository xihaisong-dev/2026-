"""Check init/stage resync and format-source interoperability in a disposable workspace."""
from pathlib import Path
import hashlib
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.agents/skills/meta-model-agent'
sys.path.insert(0, str(SKILL / 'scripts'))
from state_store import default_state, save_state
from stage_executor import prepare_stage_resources
from manifest import find_step
from gate_contracts import (GateResult, competition_source_checks, latex_texts,
                            has_superscript_citation_style)


def digest_tree(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob('*') if p.is_file()}


def main():
    current = ROOT / '模板/当前竞赛'
    expected = digest_tree(current)
    for relative in ('assets/templates/manuscript-synthesis/gmcm',
                     'references/stage_protocols/manuscript-synthesis/templates/gmcm'):
        assert digest_tree(SKILL / relative) == expected, f'Template source diverged: {relative}'
    with tempfile.TemporaryDirectory(prefix='gmcm-format-2026-') as temp:
        workspace = Path(temp)
        state = default_state(workspace, competition='gmcm', ai_disclosure='off')
        # Test-only selection; never alters the user's pending disclosure declaration.
        save_state(workspace, state)
        (workspace / '工具').mkdir()
        (workspace / '协作/赛前研读').mkdir(parents=True)
        sentinel = workspace / '协作/赛前研读/keep.txt'
        sentinel.write_text('persistent study', encoding='utf-8')
        initial_state = (workspace / '状态/工作流状态.json').read_bytes()
        prepare_stage_resources(workspace, state, find_step('MANUSCRIPT'))
        assert sentinel.read_text('utf-8') == 'persistent study'
        assert (workspace / '状态/工作流状态.json').read_bytes() == initial_state
        assert digest_tree(workspace / '模板/当前竞赛') == expected
        paper = workspace / '论文'
        paper.mkdir()
        for name in ('assets', 'sections'):
            shutil.copytree(current / name, paper / name)
        shutil.copy2(current / 'gmcmthesis.cls', paper / 'gmcmthesis.cls')
        shutil.copy2(current / 'main.tex', paper / '论文正文.tex')
        main_tex = (paper / '论文正文.tex').read_text('utf-8')
        corpus = '\n'.join(latex_texts(workspace))
        result = GateResult('TEMPLATE_TEST', 'format-source-only')
        competition_source_checks(workspace, main_tex, corpus, result)
        assert not result.issues, result.issues
        assert has_superscript_citation_style(main_tex, corpus)
        assert '排版检查项目' not in corpus, 'Demo leaked into formal source corpus'
        assert state['competition_profile']['rule_version'] == '2026'
        assert not state['competition_profile']['page_policy']['toc_required']
    print('PASS: template mirrors, stage resource refresh, persistent study, source-format gates, demo isolation.')
    print('This test does not assert manuscript quality, research-stage completion or contest acceptance.')


if __name__ == '__main__':
    main()
