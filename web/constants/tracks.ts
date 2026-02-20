export type DashboardTrackSeed = {
  id: string;
  name: string;
  description: string;
};

export const DASHBOARD_TRACK_SEEDS: DashboardTrackSeed[] = [
  { id: 'immunoassay', name: '免疫诊断', description: '抗体/抗原/化学发光相关产品' },
  { id: 'molecular', name: '分子诊断', description: 'PCR/测序/核酸检测相关产品' },
  { id: 'biochemical', name: '生化诊断', description: '酶法/比色法/代谢检测相关产品' },
  { id: 'microbiology', name: '微生物检测', description: '病原体培养与鉴定相关产品' },
  { id: 'hematology', name: '血液与凝血', description: '血细胞分析与凝血项目' },
  { id: 'poct', name: 'POCT', description: '床旁快速检测与便携设备' },
  { id: 'urine-fecal', name: '尿液与粪便', description: '尿常规、粪便常规及相关项目' },
  { id: 'other', name: '其他赛道', description: '未归类或交叉赛道产品' },
];

