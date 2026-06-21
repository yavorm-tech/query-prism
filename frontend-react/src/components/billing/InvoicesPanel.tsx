import { FileText } from "lucide-react";

export default function InvoicesPanel() {
  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h2 className="text-base font-semibold text-text text-center">Invoices</h2>
        <p className="text-xs text-text-dim">History of issued invoices for past billing periods.</p>
      </div>

      <div className="flex flex-col items-center justify-center py-20 gap-3 text-center border border-border rounded-xl bg-panel">
        <FileText size={32} className="text-text-dim opacity-40" />
        <p className="text-sm font-medium text-text-dim">No invoices yet</p>
        <p className="text-xs text-muted max-w-xs">
          Invoices will appear here once you upgrade to a paid plan and complete your first billing period.
        </p>
      </div>
    </div>
  );
}
