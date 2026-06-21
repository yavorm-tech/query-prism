import type { ReactNode } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
} from "@tanstack/react-table";
import { Table } from "flowbite-react";
import Pagination from "./Pagination";

interface Props<T> {
  data: T[];
  columns: ColumnDef<T>[];
  pageSize?: number;
  toolbar?: ReactNode;
}

export default function DataTable<T>({ data, columns, pageSize = 10, toolbar }: Props<T>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize } },
  });

  return (
    <div>
      {toolbar && <div className="mb-3">{toolbar}</div>}
      <Table>
        <Table.Head>
          {table.getHeaderGroups().map((headerGroup) =>
            headerGroup.headers.map((header) => (
              <Table.HeadCell key={header.id}>
                {header.isPlaceholder
                  ? null
                  : flexRender(header.column.columnDef.header, header.getContext())}
              </Table.HeadCell>
            ))
          )}
        </Table.Head>
        <Table.Body>
          {table.getRowModel().rows.map((row, i) => (
            <Table.Row
              key={row.id}
              className={`transition-colors hover:bg-accent/10 cursor-pointer ${i % 2 === 0 ? "bg-surface" : "bg-panel"}`}
            >
              {row.getVisibleCells().map((cell) => (
                <Table.Cell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </Table.Cell>
              ))}
            </Table.Row>
          ))}
        </Table.Body>
      </Table>
      <Pagination
        page={table.getState().pagination.pageIndex}
        pageCount={table.getPageCount()}
        onFirst={() => table.setPageIndex(0)}
        onPrev={() => table.previousPage()}
        onNext={() => table.nextPage()}
        onLast={() => table.setPageIndex(table.getPageCount() - 1)}
      />
    </div>
  );
}
