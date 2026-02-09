export type ApiResp<T> = { code: number; message: string; data: T };

export type AdminUserItem = {
  id: number;
  email: string;
  role: string;
  plan: string;
  plan_status: string;
  plan_expires_at?: string | null;
  created_at: string;
};

export type AdminMembershipGrant = {
  id: string;
  user_id: number;
  granted_by_user_id?: number | null;
  plan: string;
  start_at: string;
  end_at: string;
  reason?: string | null;
  note?: string | null;
  created_at: string;
};

export type AdminUserDetail = {
  user: AdminUserItem;
  recent_grants: AdminMembershipGrant[];
};

