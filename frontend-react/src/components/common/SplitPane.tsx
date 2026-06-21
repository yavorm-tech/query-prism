import type { ReactNode } from "react";

interface Props {
  nav: ReactNode;
  children: ReactNode;
}

export default function SplitPane({ nav, children }: Props) {
  return (
    <div className="flex flex-col sm:flex-row px-[2.5%] gap-[2.5%]">
      <div className="w-full sm:w-[15%] border-r border-border shrink-0">
        {nav}
      </div>
      <div className="w-full sm:w-[80%]">
        {children}
      </div>
    </div>
  );
}
