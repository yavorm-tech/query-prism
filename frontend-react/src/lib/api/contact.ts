import { api } from "./client";

export const sendEnterpriseContact = (b: { name: string; email: string; company_name: string; company_size: string; message: string }) =>
  api.post<{ success: boolean }>("/contact/enterprise", b).then((r) => r.data);
