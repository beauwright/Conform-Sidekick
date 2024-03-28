import { Button } from "./ui/button";
import { RadioGroup, RadioGroupItem } from "./ui/radio-group";
import { FC, useEffect } from "react";
import { useResolveContext } from "@/ResolveContext";
import { Label } from "@/components/ui/label";

interface ScopeSelectorProps {
    setShowDataTable: (value: boolean) => void;
    projOrTimelineSelected: string;
    setProjOrTimelineSelected: (value: string) => void;
    typeOfMediaDisplayString: string
  }
  
  const ScopeSelector: FC<ScopeSelectorProps> = ({ setShowDataTable, projOrTimelineSelected, setProjOrTimelineSelected, typeOfMediaDisplayString }) => {
    const context = useResolveContext();
    const { currentProject, currentTimeline } = context || {};
  
    useEffect(() => {
      if (currentTimeline === "") {
        setProjOrTimelineSelected("project");
      }
    }, [currentTimeline]);
  
    return (
      <>
        <div className="flex justify-center select-none">
          <h2 className="dark:text-slate-300 text-sm px-5 italic">
            Current Project: {currentProject}
          </h2>
          <h2 className="dark:text-slate-300 text-sm px-5 italic">
            Current Timeline: {currentTimeline}
          </h2>
        </div>
        <div className="flex justify-center select-none">
          <div className="flex m-2 w-1/2 justify-around bg-slate-50/60 dark:bg-slate-800 rounded dark:text-white">
            <RadioGroup
              defaultValue="project"
              value={projOrTimelineSelected}
              onValueChange={(value) => {
                setProjOrTimelineSelected(value);
              }}
              className="p-5"
            >
              <h2 className="font-semibold">
                Where to Look For {typeOfMediaDisplayString}
              </h2>
              <div className="flex items-center gap-1">
                <RadioGroupItem value="project" id="project" />
                <Label htmlFor="r1">Project-wide</Label>
              </div>
              <div className="flex items-center gap-1">
                <RadioGroupItem
                  value="timeline"
                  id="timeline"
                  disabled={currentTimeline === ""}
                />
                <Label htmlFor="r2">Current Timeline</Label>
              </div>
            </RadioGroup>
          </div>
        </div>
        <div className="flex justify-center p-5">
          <Button
            onClick={() => {
              setShowDataTable(true);
            }}
          >
            Run
          </Button>
        </div>
      </>
    );
  };

  export default ScopeSelector