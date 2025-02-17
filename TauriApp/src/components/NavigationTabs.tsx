import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
function NavigationTabs({
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
        className="p-10"
      >
        <TabsList className="w-auto flex flex-row flex-wrap h-auto max-w-fit mx-auto">
          <TabsTrigger
            value="photos"
            className="text-sm md:text-lg w-72"
            onClick={() => onViewChange("photos")}
          >
            Fix Odd Resolution Photos
          </TabsTrigger>
          <TabsTrigger
            value="interlaced"
            className="text-sm md:text-lg w-72"
            onClick={() => onViewChange("interlaced")}
          >
            Identify Interlaced Footage
          </TabsTrigger>
          <TabsTrigger
            value="compound"
            className="text-sm md:text-lg w-72"
            onClick={() => onViewChange("compound")}
          >
            Identify Compound Clips
          </TabsTrigger>
          <TabsTrigger
            value="scale-multiplier"
            className="text-sm md:text-lg w-72"
            onClick={() => onViewChange("scale-multiplier")}
          >
            Scale Multiplier
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </>
  );
}
export default NavigationTabs;
