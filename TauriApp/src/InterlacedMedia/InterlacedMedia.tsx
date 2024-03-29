import { columns } from "./columns";
import { useState } from "react";
import { Convert as ConvertInterlacedMedia, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
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

            conversionFunction: ConvertInterlacedMedia.toSelectedMedia,
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
