import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';

export default async function AdminRawDocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>raw_document</CardTitle>
          <CardDescription>原始文档详情页（占位）</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mono">raw_document_id: {decodeURIComponent(id || '')}</div>
        </CardContent>
      </Card>
    </div>
  );
}
