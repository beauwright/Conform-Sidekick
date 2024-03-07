import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";
import { useWebSocket } from "@/ResolveContext";
import { DataTable } from "./data-table";
import { Payment, columns } from "./columns";
import { useState } from "react";
async function getData(): Promise<Payment[]> {
  // Fetch data from your API here.
  return [
    {
      id: "728ed52f",
      amount: 100,
      status: "pending",
      email: "m@example.com",
    },
  ];
}

const data = await getData();

function EvenResPhotos() {
  const context = useWebSocket();
  // Ensure that context is not null before destructuring
  const { currentProject, currentTimeline } = context || {};
  const [showDataTable, setShowDataTable] = useState(false);
  return (
    <>
      {currentProject === "" ? (
        <>
          <div className="text-center">
            <h1 className="text-xl font-light text-slate-900 dark:text-slate-50">Connecting to DaVinci Resolve</h1>
            <div role="status">
              <svg
                aria-hidden="true"
                className="inline w-8 h-8 text-gray-200 animate-spin dark:text-gray-600 fill-blue-600"
                viewBox="0 0 100 101"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M100 50.5908C100 78.2051 77.6142 100.591 50 100.591C22.3858 100.591 0 78.2051 0 50.5908C0 22.9766 22.3858 0.59082 50 0.59082C77.6142 0.59082 100 22.9766 100 50.5908ZM9.08144 50.5908C9.08144 73.1895 27.4013 91.5094 50 91.5094C72.5987 91.5094 90.9186 73.1895 90.9186 50.5908C90.9186 27.9921 72.5987 9.67226 50 9.67226C27.4013 9.67226 9.08144 27.9921 9.08144 50.5908Z"
                  fill="currentColor"
                />
                <path
                  d="M93.9676 39.0409C96.393 38.4038 97.8624 35.9116 97.0079 33.5539C95.2932 28.8227 92.871 24.3692 89.8167 20.348C85.8452 15.1192 80.8826 10.7238 75.2124 7.41289C69.5422 4.10194 63.2754 1.94025 56.7698 1.05124C51.7666 0.367541 46.6976 0.446843 41.7345 1.27873C39.2613 1.69328 37.813 4.19778 38.4501 6.62326C39.0873 9.04874 41.5694 10.4717 44.0505 10.1071C47.8511 9.54855 51.7191 9.52689 55.5402 10.0491C60.8642 10.7766 65.9928 12.5457 70.6331 15.2552C75.2735 17.9648 79.3347 21.5619 82.5849 25.841C84.9175 28.9121 86.7997 32.2913 88.1811 35.8758C89.083 38.2158 91.5421 39.6781 93.9676 39.0409Z"
                  fill="currentFill"
                />
              </svg>
              <span className="sr-only">Loading...</span>
            </div>
          </div>
        </>
      ) : (
        <>
          {showDataTable === false ? (
            <>
              <div className="flex justify-center">
                <h2 className="dark:text-slate-300 text-sm px-5 italic">
                  Current Project: {currentProject}
                </h2>
                <h2 className="dark:text-slate-300 text-sm px-5 italic">
                  Current Timeline: {currentTimeline}
                </h2>
              </div>
              <div className="flex justify-center ">
                <div className="flex w-2/3 justify-around items-center bg-slate-50/60 dark:bg-slate-800 rounded dark:text-white">
                  <RadioGroup defaultValue="comfortable" className="p-5">
                    <h2 className="font-semibold">Where to Look</h2>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="default" id="r1" />
                      <Label htmlFor="r1">Project-wide</Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="comfortable" id="r2" />
                      <Label htmlFor="r2">Current Timeline</Label>
                    </div>
                  </RadioGroup>
                  <Separator
                    orientation="vertical"
                    className="h-20 dark:bg-slate-500"
                  />
                  <RadioGroup defaultValue="comfortable" className="p-5">
                    <h2 className="font-semibold">What To Do</h2>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="default" id="r1" />
                      <Label htmlFor="identify">
                        Only Identify Odd Resolution Media
                      </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="comfortable" id="r2" />
                      <Label htmlFor="convert">
                        Identify and Convert Odd Resolution Media
                      </Label>
                    </div>
                  </RadioGroup>
                </div>
              </div>
              <div className="flex justify-center p-5">
                <Button onClick={() => {setShowDataTable(true)}}>Run</Button>
              </div>
            </>
          ) : (
            <div className="w-11/12 mx-auto">
              <DataTable columns={columns} data={data} />
            </div>
          )}
        </>
      )}
    </>
  );
}

export default EvenResPhotos;
