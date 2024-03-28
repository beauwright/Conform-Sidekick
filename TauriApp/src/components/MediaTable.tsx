import React, { useEffect, useState } from 'react';
import { DataTable } from "../components/ui/data-table";
import LoadingStatus from "@/LoadingStatus";
import ScopeSelector from "@/components/ScopeSelector";
import { getObjectFromPythonSidecar } from '@/lib/utils';

// Updated DataFetchParameters to include separate keys for project and timeline
type DataFetchParameters = {
    projectKey: string; // Key used when projOrTimelineSelected is 'project'
    timelineKey: string; // Key used when projOrTimelineSelected is 'timeline'
    conversionFunction: (data: any) => any;
};

type MediaTableProps = {
    dataFetchParameters: DataFetchParameters;
    columns: any[];
    additionalUI?: React.ReactNode | (() => React.ReactNode);
    buttonProps?: {
        buttonLabel: string;
        buttonFunction: VoidFunction;
    };
    typeOfMediaDisplayString: string;
};

const MediaTable: React.FC<MediaTableProps> = ({
    dataFetchParameters,
    columns,
    additionalUI,
    buttonProps,
    typeOfMediaDisplayString
}) => {
    const [showDataTable, setShowDataTable] = useState(false);
    const [tableData, setTableData] = useState(null);
    const [projOrTimelineSelected, setProjOrTimelineSelected] = useState("project");
    const [rowSelection, setRowSelection] = useState({});

    const getData = async () => {
        const dataKey = projOrTimelineSelected === 'project' ? dataFetchParameters.projectKey : dataFetchParameters.timelineKey;
        try {
            const data = await getObjectFromPythonSidecar(
                [dataKey],
                dataFetchParameters.conversionFunction
            );
            console.log(`${typeOfMediaDisplayString} data:`, data);
            return data.selectedMedia;
        } catch (error) {
            console.log(`Error fetching ${typeOfMediaDisplayString.toLowerCase()} data`, error);
            return [];
        }
    };

    useEffect(() => {
        async function fetchData() {
            if (showDataTable) {
                const data = await getData();
                setTableData(data);
            }
        }

        fetchData();
    }, [showDataTable, projOrTimelineSelected]);

    const renderAdditionalUI = () => {
        if (typeof additionalUI === 'function') {
            return additionalUI();
        }
        return additionalUI;
    };

    return (
        <>
            {showDataTable ? (
                tableData ? (
                    <div className="w-11/12 mx-auto pb-5">
                        <DataTable
                            columns={columns}
                            data={tableData || []}
                            rowSelection={rowSelection}
                            setRowSelection={setRowSelection}
                            buttonProps={buttonProps} // Directly passed to DataTable
                        />
                        {renderAdditionalUI()}
                    </div>
                ) : (
                    <LoadingStatus loadingText={`Finding ${typeOfMediaDisplayString}`} />
                )
            ) : (
                <ScopeSelector
                    setShowDataTable={setShowDataTable}
                    projOrTimelineSelected={projOrTimelineSelected}
                    setProjOrTimelineSelected={setProjOrTimelineSelected}
                    typeOfMediaDisplayString={typeOfMediaDisplayString}
                />
            )}
        </>
    );
};

export default MediaTable;
