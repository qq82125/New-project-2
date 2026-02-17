export const ADMIN_TEXT = {
  workbenchTitle: '管理工作台',
  menuTitle: '后台菜单',
  breadcrumbFallback: '管理后台',
  modules: {
    home: {
      title: '管理后台总览',
      description: '围绕待处理、冲突和数据源健康度的日常工作台。',
    },
    pending: {
      title: '待处理记录管理',
      description: '仅管理员可访问。用于跟踪注册锚点未解析记录的积压情况。',
    },
    conflicts: {
      title: '冲突队列管理',
      description: '仅管理员可访问。用于处理字段级无法自动裁决的冲突。',
    },
    sources: {
      title: '数据源运维配置',
      description: '管理 Source Registry 运行配置：开关、优先级、默认证据等级与解析参数。',
    },
    udiLinks: {
      title: 'UDI 待映射管理',
      description: '用于处理 pending_udi_links 队列，并手动完成 DI 到注册证号的绑定。',
    },
    users: {
      title: '用户与会员管理',
      description: '用于搜索用户并执行开通、续费、暂停、撤销等会员操作。',
    },
    userDetail: {
      title: '用户详情',
      description: '查看用户与会员状态，并执行单用户的精细化管理操作。',
    },
    contact: {
      title: '联系信息',
      description: '用于配置 /contact 页面展示的联系方式与引导入口。',
    },
  },
} as const;

export const ADMIN_ROLE_ZH: Record<string, string> = {
  admin: '管理员',
  user: '普通用户',
};

export const ADMIN_PENDING_STATUS_ZH: Record<string, string> = {
  open: '待处理',
  resolved: '已解决',
  ignored: '已忽略',
  pending: '待补充',
  all: '全部',
};

export const ADMIN_CONFLICT_STATUS_ZH: Record<string, string> = {
  open: '待裁决',
  resolved: '已裁决',
  all: '全部',
};

export const ADMIN_UDI_LINK_STATUS_ZH: Record<string, string> = {
  PENDING: '待处理',
  RETRYING: '重试中',
  RESOLVED: '已解决',
  ALL: '全部',
};

export const ADMIN_NAV_GROUPS: Array<{
  title: string;
  items: Array<{ href: string; label: string; icon: string }>;
}> = [
  {
    title: '工作台',
    items: [
      { href: '/admin', label: '总览', icon: 'OV' },
      { href: '/admin/pending', label: '待处理记录', icon: 'PD' },
      { href: '/admin/conflicts', label: '冲突处理', icon: 'CF' },
    ],
  },
  {
    title: '数据治理',
    items: [
      { href: '/admin/sources', label: '数据源配置', icon: 'SR' },
      { href: '/admin/udi-links', label: 'UDI 待映射', icon: 'UD' },
    ],
  },
  {
    title: '系统管理',
    items: [
      { href: '/admin/users', label: '用户与会员', icon: 'US' },
      { href: '/admin/contact', label: '联系信息', icon: 'CT' },
    ],
  },
];

export function getAdminBreadcrumb(pathname: string): string {
  const p = String(pathname || '/admin');
  if (p === '/admin') return '总览';
  if (p.startsWith('/admin/pending')) return '待处理记录';
  if (p.startsWith('/admin/conflicts')) return '冲突处理';
  if (p.startsWith('/admin/sources') || p.startsWith('/admin/data-sources')) return '数据源配置';
  if (p.startsWith('/admin/udi-links')) return 'UDI 待映射';
  if (p.startsWith('/admin/users')) return '用户与会员';
  if (p.startsWith('/admin/contact')) return '联系信息';
  return ADMIN_TEXT.breadcrumbFallback;
}
