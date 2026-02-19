'use client';

import { useState } from 'react';
import { Button } from '../ui/button';
import { toast } from '../ui/use-toast';
import UnifiedProGate from '../plan/UnifiedProGate';

export default function SearchExportActions({ canExport, exportHref }: { canExport: boolean; exportHref: string }) {
  const [showGate, setShowGate] = useState(false);

  if (canExport) {
    return (
      <a className="ui-btn" href={exportHref}>
        导出 CSV
      </a>
    );
  }

  return (
    <div className="grid" style={{ gap: 10, width: '100%' }}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <Button
          type="button"
          onClick={() => {
            setShowGate(true);
            toast({ title: '升级到 Pro', description: '解锁导出与高级分析能力' });
          }}
        >
          导出 CSV
        </Button>
      </div>
      {showGate ? <UnifiedProGate showProPageEntry /> : null}
    </div>
  );
}
