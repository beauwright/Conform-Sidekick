import { DataTable } from "../components/ui/data-table";
import { columns } from "./columns";
import { useEffect, useState } from "react";
import { Convert as ConvertOddResMedia, SelectedMediaElement } from "@/jsonParse/SelectedMedia";
import { getObjectFromPythonSidecar } from "@/lib/utils";
import LoadingStatus from "@/LoadingStatus";
import ScopeSelector from "@/components/ScopeSelector"
async function getData(projOrTimelineSelected: string): Promise<SelectedMediaElement[]> {
    // Determine the argument based on the selected radio option
    const dataKey = projOrTimelineSelected === "timeline" ? ["interlacedInTimeline"] : ["interlacedInProject"];
    try {
        const interlacedMedia = await getObjectFromPythonSidecar(
            dataKey,
            ConvertOddResMedia.toSelectedMedia
        );
        console.log("interlacedMedia", interlacedMedia);
        return interlacedMedia.selectedMedia;
    } catch (error) {
        console.log("error fetching interlaced media data", error);
        return [];
    }
}

function InterlacedMedia() {
    const [showDataTable, setShowDataTable] = useState(false);
    const [tableData, setTableData] = useState<SelectedMediaElement[] | null>(null);
    const [projOrTimelineSelected, setProjOrTimelineSelected] = useState("project");
    type RowSelection = { [key: number]: boolean };
    // Table state
    const [rowSelection, setRowSelection] = useState<RowSelection>({});



    useEffect(() => {
        async function fetchData() {
            const data = await getData(projOrTimelineSelected);
            console.log("data is", data);
            setTableData(data);
        }

        if (showDataTable) {
            fetchData();
        }
    }, [showDataTable]);

    return (
        <>
            {showDataTable ? (
                tableData ? (
                    <div className="w-11/12 mx-auto pb-5">
                        <DataTable
                            columns={columns}
                            data={tableData}
                            rowSelection={rowSelection}
                            setRowSelection={setRowSelection}
                        />
                    </div>
                ) : (
                    <LoadingStatus loadingText="Finding interlaced media" />
                )
            ) : (
                <ScopeSelector setShowDataTable={setShowDataTable} projOrTimelineSelected={projOrTimelineSelected} setProjOrTimelineSelected={setProjOrTimelineSelected} typeOfMediaDisplayString="Interlaced Media" />
            )}
        </>
    );
}

export default InterlacedMedia;
