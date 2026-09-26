"""Plot the mean paired no-L2/L2 ratio without changing adopted results."""
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '图表/runs/20260926-A-q123-complete-delivery'
source = OUT / 'evidence.json'
rows = sorted((p for p in json.loads(source.read_text('utf-8'))['points']
               if p['problem'] == 3), key=lambda p: p['cores'])
assert [p['cores'] for p in rows] == [1, 2, 3, 4, 5]
assert all(p['cases'] == 100 for p in rows)
x = [p['cores'] for p in rows]
y = [p['mean_same_plan_cache_ratio'] for p in rows]
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'font.size': 12,
                     'axes.unicode_minus': False, 'pdf.fonttype': 42})
fig, ax = plt.subplots(figsize=(7.2, 4.5), layout='constrained')
ax.axhline(1, color='0.5', linestyle='--', linewidth=1)
ax.plot(x, y, marker='o', color='#21618C', linewidth=2, markersize=6)
for k, value in zip(x, y):
    ax.annotate(f'{value:.4f}', (k, value), xytext=(0, 11),
                textcoords='offset points', ha='center', fontsize=12)
ax.set(xlabel='核心数', ylabel='同方案无 L2 / 开启 L2 的平均时间比',
       xticks=x, xlim=(0.7, 5.3), ylim=(0.998, 1.038))
ax.set_yticks([1, 1.01, 1.02, 1.03])
ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
ax.grid(axis='y', alpha=.25)
ax.spines[['top', 'right']].set_visible(False)
for ext in ('png', 'pdf'):
    fig.savefig(OUT / f'l2_independent_gain.{ext}', dpi=300)
plt.close(fig)
(OUT / 'l2_independent_gain.data.json').write_text(json.dumps({
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'definition': 'mean_i(T_no_L2_i_k / T_L2_i_k), identical plan in each pair',
    'cases_per_core': 100, 'cores': x, 'mean_ratio': y,
    'note': 'Ratio axis is truncated to display small differences; dashed line is no gain.'
}, ensure_ascii=False, indent=2), encoding='utf-8')
manifest = ROOT / '图表/figure_manifest.json'
m = json.loads(manifest.read_text('utf-8'))
path = (OUT / 'l2_independent_gain.pdf').relative_to(ROOT).as_posix()
m['figures'] = [p for p in m['figures'] if p.get('path') != path]
m['figures'].append(dict(path=path, claim='同一方案只切换L2的逐图平均加速比',
    source=source.relative_to(ROOT).as_posix(), reader_task='区分硬件独立收益与跨方案综合收益',
    publish=False, placement='standalone'))
manifest.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
print(path)
