import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
function Toolbar({
  defaultValue,
  onViewChange,
}: {
  defaultValue: string;
  onViewChange: (view: string) => void;
}) {
  return (
    <>
      <Tabs
        defaultValue={defaultValue}
        className="w-[400] px-10 pt-10 pb-0 lg:px-20 lg:pt-20"
      >
        <TabsList className="grid w-full grid-cols-3 h-12">
          <TabsTrigger
            value="photos"
            className="text-lg"
            onClick={() => onViewChange("photos")}
          >
            Fix Odd Resolution Photos
          </TabsTrigger>
          <TabsTrigger
            value="interlaced"
            className="text-lg"
            onClick={() => onViewChange("interlaced")}
          >
            Identify Interlaced Footage
          </TabsTrigger>
          <TabsTrigger
            value="compound"
            className="text-lg"
            onClick={() => onViewChange("compound")}
          >
            Identify Compound Clips
          </TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="grid w-full grid-cols-3 pt-2 pb-10 px-10">
        <Popover>
          <PopoverTrigger>
            <InfoCircledIcon className="text-slate-400" />
          </PopoverTrigger>
          <PopoverContent align="start">
            <h3 className="text-sm break-words">
              Odd resolution media can cause export errors when rendering at
              source resolution for codecs that do not support odd resolutions.
              <br />
              <br />
              This tool allows you to quickly identify any media with odd
              resolutions and can fix the issue automatically if the media is a
              photo.
            </h3>
          </PopoverContent>
        </Popover>
        <Popover>
          <PopoverTrigger>
            <InfoCircledIcon className="text-slate-400" />
          </PopoverTrigger>
          <PopoverContent align="start">
            <h3 className="text-sm break-words">
              Interlaced footage often needs special care from the colorist.
              <br />
              <br />
              This tool allows you to identify interlaced footage quickly.
            </h3>
          </PopoverContent>
        </Popover>
        <Popover>
          <PopoverTrigger>
            <InfoCircledIcon className="text-slate-400" />
          </PopoverTrigger>
          <PopoverContent align="start">
            <h3 className="text-sm break-words">
              Compound clips can require special care from the colorist.
              <br />
              <br />
              This tool allows you to identify compound clips quickly.
            </h3>
          </PopoverContent>
        </Popover>
      </div>
    </>
  );
}
export default Toolbar;
