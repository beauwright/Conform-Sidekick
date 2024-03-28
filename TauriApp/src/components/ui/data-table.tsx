"use client";
import {
  useNavigate,
} from "react-router-dom";
import {
  ColumnDef,
  ColumnFiltersState,
  RowSelectionState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  rowSelection: { [key: string]: boolean };
  setRowSelection: (newSelection: RowSelectionState | ((prevState: RowSelectionState) => RowSelectionState)) => void;
  buttonProps?: {
    buttonLabel: string;
    buttonFunction: VoidFunction;
  };
}



export function DataTable<TData, TValue>({
  columns,
  data,
  buttonProps,
  rowSelection,
  setRowSelection,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>(
    []
  );
  const [columnVisibility, setColumnVisibility] =
    React.useState<VisibilityState>({});

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
  });
  const navigate = useNavigate();
  const [shouldReload, setShouldReload] = useState(false);

  // Function to navigate back to selection screen
  const handleGoBack = () => {
    setShouldReload(true);
    navigate(-2); // Navigate back past table and loading screen
  };

  useEffect(() => {
    if (shouldReload) {
      setShouldReload(false); // Reset the reload trigger
    }
  }, [location.pathname]);

  return (
    <>
      <div className="flex-1 text-sm text-muted-foreground dark:text-white break-all">
        {table.getFilteredSelectedRowModel().rows.length} of {table.getFilteredRowModel().rows.length} row(s) selected.
      </div>
      <div className="rounded-md border dark:text-white">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex justify-center">
        {/* Conditionally render the button if buttonProps is provided */}
        {buttonProps && (
          <div className="flex justify-center">
            <Button
              className="m-5"
              disabled={table.getFilteredSelectedRowModel().rows.length === 0}
              onClick={() => buttonProps.buttonFunction()}
            >
              {buttonProps.buttonLabel}
            </Button>
          </div>
        )}
        <div className="flex justify-center">
          <Button variant="outline" className="m-5 dark:text-slate-200" onClick={handleGoBack}>Go back</Button>
        </div>
      </div>
    </>
  );
}
