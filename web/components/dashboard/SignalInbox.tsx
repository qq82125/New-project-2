import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import UnifiedTable from '../table/UnifiedTable';
import type { UnifiedTableRow } from '../table/columns';

export default function SignalInbox({ rows }: { rows: UnifiedTableRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Today Signals Inbox</CardTitle>
        <CardDescription>统一列表组件，点击行跳转 Search。</CardDescription>
      </CardHeader>
      <CardContent>
        <UnifiedTable rows={rows} emptyText="暂无信号入口" />
      </CardContent>
    </Card>
  );
}

