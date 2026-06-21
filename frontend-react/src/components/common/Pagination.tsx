import { Button } from "flowbite-react";

interface Props {
  page: number;
  pageCount: number;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
}

export default function Pagination({ page, pageCount, onFirst, onPrev, onNext, onLast }: Props) {
  const first = page <= 0, last = page >= pageCount - 1;
  return (
    <div className="mt-3 flex items-center justify-center gap-2 text-sm">
      <Button size="xs" color="light" disabled={first} onClick={onFirst}>First</Button>
      <Button size="xs" color="light" disabled={first} onClick={onPrev}>Prev</Button>
      <span className="px-2 font-medium text-accent">{page + 1}</span>
      <Button size="xs" color="light" disabled={last} onClick={onNext}>Next</Button>
      <Button size="xs" color="light" disabled={last} onClick={onLast}>Last</Button>
    </div>
  );
}
