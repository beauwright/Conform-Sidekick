import { columns } from "./columns";
import { useState } from "react";
import { Convert as ConvertCompoundClips, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import MediaTable, { RowSelection } from "@/components/MediaTable";

function CompoundClips() {
    const [tableData, setTableData] = useState<SelectedMediaElement[] | null>(null);
    const [rowSelection, setRowSelection] = useState<RowSelection>({});

    return (
        <MediaTable
          typeOfMediaDisplayString="Compound Clips"
          dataFetchParameters={{
            projectKey: "compoundClipsInProject",
            timelineKey: "compoundClipsInTimeline",

            conversionFunction: ConvertCompoundClips.toSelectedMedia,
          }}
          selection={rowSelection}
          setSelection={setRowSelection}
          columns={columns}
          tableData={tableData}
          setTableData={setTableData}
        />
    );
}

export default CompoundClips;
