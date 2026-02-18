import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { EmptyState, ErrorState } from '../States';
import ProUpgradeHint from '../plan/ProUpgradeHint';
import { LRI_RISK_ZH, labelFrom } from '../../constants/display';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';

export type LriScore = {
  risk_level: string;
  lri_norm: number;
  tte_days?: number | null;
  model_version?: string | null;
  calculated_at?: string | null;
  methodology_code?: string | null;
  methodology_name_cn?: string | null;
  renewal_count?: number | null;
  competitive_count?: number | null;
  gp_new_12m?: number | null;
  tte_score?: number | null;
  rh_score?: number | null;
  cd_score?: number | null;
  gp_score?: number | null;
  lri_total?: number | null;
};

export default function LriCard({
  score,
  isPro,
  loadingError,
}: {
  score: LriScore | null;
  isPro: boolean;
  loadingError?: string | null;
}) {
  const risk = String(score?.risk_level || '').toUpperCase();
  const badgeVariant =
    risk === 'LOW' ? 'success' : risk === 'MID' ? 'warning' : risk === 'HIGH' ? 'danger' : risk === 'CRITICAL' ? 'danger' : 'muted';
  const normPct = Number(score?.lri_norm || 0) * 100;

  return (
    <Card>
      <CardHeader>
        <CardTitle>LRI 风险指标 (V1)</CardTitle>
        <CardDescription>基于到期压力、续期历史、赛道竞争与近期增长的综合风险刻画（每日重算）。</CardDescription>
      </CardHeader>
      <CardContent className="grid">
        {loadingError ? <ErrorState text={`LRI 加载失败：${loadingError}`} /> : null}
        {!loadingError && !score ? <EmptyState text="暂无 LRI 结果（可能尚未计算）。" /> : null}

        {score ? (
          <div className="grid">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant={badgeVariant}>风险等级: {labelFrom(LRI_RISK_ZH, risk)}</Badge>
              <Badge variant="muted">综合分: {normPct.toFixed(1)}%</Badge>
              <Badge variant="muted">到期剩余: {score.tte_days ?? '-'} 天</Badge>
              {score.methodology_code || score.methodology_name_cn ? (
                <Badge variant="muted">方法学: {score.methodology_name_cn || score.methodology_code}</Badge>
              ) : null}
            </div>

            {isPro ? (
              <div className="grid">
                <div className="columns-2">
                  <div>
                    <div className="muted">续期次数</div>
                    <div>{score.renewal_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="muted">赛道竞争数</div>
                    <div>{score.competitive_count ?? 0}</div>
                  </div>
                  <div>
                    <div className="muted">赛道新增 (12 个月)</div>
                    <div>{score.gp_new_12m ?? 0}</div>
                  </div>
                  <div>
                    <div className="muted">模型</div>
                    <div>{score.model_version || 'lri_v1'}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">TTE: {score.tte_score ?? '-'}</Badge>
                  <Badge variant="muted">RH: {score.rh_score ?? '-'}</Badge>
                  <Badge variant="muted">CD: {score.cd_score ?? '-'}</Badge>
                  <Badge variant="muted">GP: {score.gp_score ?? '-'}</Badge>
                  <span className="muted">
                    · 计算时间 {String(score.calculated_at || '').slice(0, 19).replace('T', ' ')}
                  </span>
                </div>
              </div>
            ) : (
              <ProUpgradeHint
                text="升级专业版查看 LRI 构成分项（TTE/RH/CD/GP）与竞争、增长等详情。"
                ctaHref={PRO_TRIAL_HREF}
                ctaLabel={PRO_COPY.banner.free_cta}
              />
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
