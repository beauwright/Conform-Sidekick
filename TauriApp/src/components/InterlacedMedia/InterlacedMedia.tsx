import { columns } from "./columns";
import { useState } from "react";
import { SelectedMediaSchema, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import MediaTable, { RowSelection } from "@/components/MediaTable";

function InterlacedMedia() {
    const [tableData, setTableData] = useState<SelectedMediaElement[] | null>(null);

    const [rowSelection, setRowSelection] = useState<RowSelection>({});

    return (
        <MediaTable
          typeOfMediaDisplayString="Interlaced Media"
          dataFetchParameters={{
            projectKey: "interlacedInProject",
            timelineKey: "interlacedInTimeline",

            conversionFunction: SelectedMediaSchema.parse,
          }}
          selection={rowSelection}
          setSelection={setRowSelection}
          columns={columns}
          tableData={tableData}
          setTableData={setTableData}
        />
    );
}

export default InterlacedMedia;
