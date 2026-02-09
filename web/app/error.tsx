'use client';

import { ErrorState } from '../components/States';
import { useEffect } from 'react';
import { toast } from '../components/ui/use-toast';
import { Button } from '../components/ui/button';

export default function Error({ reset }: { reset: () => void }) {
  useEffect(() => {
    toast({ variant: 'destructive', title: '页面错误', description: '页面加载失败，请稍后重试。' });
  }, []);

  return (
    <div className="grid">
      <ErrorState text="页面加载失败，请稍后重试" />
      <Button onClick={reset}>重试</Button>
    </div>
  );
}
