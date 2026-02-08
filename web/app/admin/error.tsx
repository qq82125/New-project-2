'use client';

import { useEffect } from 'react';
import { ErrorState } from '../../components/States';
import { Button } from '../../components/ui/button';
import { toast } from '../../components/ui/use-toast';

export default function Error({ reset }: { reset: () => void }) {
  useEffect(() => {
    toast({ variant: 'destructive', title: '管理后台错误', description: '加载失败，请稍后重试。' });
  }, []);

  return (
    <div className="grid">
      <ErrorState text="管理后台加载失败，请稍后重试" />
      <Button onClick={reset}>重试</Button>
    </div>
  );
}

