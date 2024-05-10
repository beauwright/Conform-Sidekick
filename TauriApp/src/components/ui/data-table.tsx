import { useNavigate } from "react-router-dom";
import {
  ColumnDef,
  ColumnFiltersState,
  FilterFn,
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
import { TrackFilter } from "./track-filter";
import { SelectedMedia } from "@/jsonParse/SelectedMedia";

declare module "@tanstack/table-core" {
  interface FilterFns {
    rangeFilter: FilterFn<SelectedMedia>;
  }
}
interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  rowSelection: { [key: string]: boolean };
  setRowSelection: (
    newSelection:
      | RowSelectionState
      | ((prevState: RowSelectionState) => RowSelectionState)
  ) => void;
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
    filterFns: {
      rangeFilter: (row, columnId, filterValue) => {
        // Ensure filter values are defined and are numbers
        const tracks: number[] = row.getValue(columnId) as number[];
        if (filterValue && !isNaN(filterValue.from) && !isNaN(filterValue.to)) {
          return tracks.some(
            (track) =>
              track >= parseInt(filterValue.from, 10) &&
              track <= parseInt(filterValue.to, 10)
          );
        }
        return true; // Return all if no filter or invalid filter is applied
      },
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

  useEffect(() => {
    console.log("Current filters:", columnFilters);
  }, [columnFilters]);

  return (
    <>
      <div className="flex-1 text-sm text-muted-foreground dark:text-white mb-2">
        <div className="mb-2">
          <TrackFilter setColumnFilters={setColumnFilters} />
        </div>
        {table.getFilteredSelectedRowModel().rows.length} of{" "}
        {table.getFilteredRowModel().rows.length} row(s) selected.
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
          <TableBody className="[overflow-wrap:anywhere] hyphens-auto max-w-fit">
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
          <Button
            variant="outline"
            className="m-5 dark:text-slate-200"
            onClick={handleGoBack}
          >
            Go back
          </Button>
        </div>
      </div>
    </>
  );
}
