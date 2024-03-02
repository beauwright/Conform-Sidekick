import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Separator } from "@/components/ui/separator";

function EvenResPhotos() {
  return (
    <>
      <div className="flex justify-center">
        <h2 className="dark:text-slate-300 text-sm px-5 italic">
          Current Project: Turkey IGF
        </h2>
        <h2 className="dark:text-slate-300 text-sm px-5 italic">
          Current Timeline: Ep 2
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
        <Button onClick={() => {}}>Run</Button>
      </div>
    </>
  );
}

export default EvenResPhotos;
