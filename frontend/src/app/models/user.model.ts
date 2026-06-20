export interface User {
  _id?: string;
  user_id?: string;
  username: string;
  email?: string;
  role?: string;
  contact_preference?: string;
  created_at?: string;
  display_name?: string;
  phone?: string;
  has_profile_image?: boolean;
  token?: string;
}
