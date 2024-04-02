import React, { useEffect, useState } from 'react';
import { DataTable } from "../components/ui/data-table";
import LoadingStatus from "@/LoadingStatus";
import ScopeSelector from "@/components/ScopeSelector";
import { getObjectFromPythonSidecar } from '@/lib/utils';
import { SelectedMediaElement } from '@/jsonParse/SelectedMedia';
import { useToast } from './ui/use-toast';
import { Toaster } from './ui/toaster';

type DataFetchParameters = {
    projectKey: string; // Key used when projOrTimelineSelected is 'project'
    timelineKey: string; // Key used when projOrTimelineSelected is 'timeline'
    conversionFunction: (data: any) => any;
};

export type RowSelection = { [key: number]: boolean };

type MediaTableProps = {
    dataFetchParameters: DataFetchParameters;
    columns: any[];
    additionalUI?: React.ReactNode | (() => React.ReactNode);
    buttonProps?: {
        buttonLabel: string;
        buttonFunction: VoidFunction;
    };
    typeOfMediaDisplayString: string;
    selection: RowSelection;
    setSelection: React.Dispatch<React.SetStateAction<RowSelection>>;
    tableData: SelectedMediaElement[] | null
    setTableData: React.Dispatch<React.SetStateAction<SelectedMediaElement[] | null>>
    showDataTableProp?: boolean;
};

const MediaTable: React.FC<MediaTableProps> = ({
    dataFetchParameters,
    columns,
    additionalUI,
    buttonProps,
    typeOfMediaDisplayString,
    selection,
    setSelection,
    tableData,
    setTableData,
    showDataTableProp
}) => {
    const [showDataTable, setShowDataTable] = useState(false);

    const [projOrTimelineSelected, setProjOrTimelineSelected] = useState("project");
    const { toast } = useToast();

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
            const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
            toast({
                variant: "destructive",
                title: `Error fetching ${typeOfMediaDisplayString.toLowerCase()} data`,
                description: errorMessage,
            });
            return [];
        }
    };

    useEffect(() => {
        async function fetchData() {
            if (showDataTable && (showDataTableProp === undefined|| showDataTableProp===false)) {
                const data = await getData();
                setTableData(data);
            }
        }

        fetchData();
    }, [showDataTable, projOrTimelineSelected]);

    useEffect(() => {
        if (showDataTableProp !== undefined) {
            setShowDataTable(showDataTableProp);
        }
    }, [showDataTableProp]);

    const renderAdditionalUI = () => {
        if (typeof additionalUI === 'function') {
            return additionalUI();
        }
        return additionalUI;
    };

    return (
        <>
            <Toaster />
            {showDataTable ? (
                tableData ? (
                    <div className="w-11/12 mx-auto pb-5">
                        <DataTable
                            columns={columns}
                            data={tableData || []}
                            rowSelection={selection!}
                            setRowSelection={setSelection!}
                            buttonProps={buttonProps}
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
