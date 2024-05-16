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
        className="w-[400] p-10 lg:px-20 lg:pt-20"
      >
        <TabsList className="grid w-full grid-cols-3 md:h-12">
          <TabsTrigger
            value="photos"
            className="text-sm md:text-lg"
            onClick={() => onViewChange("photos")}
          >
            Fix Odd Resolution Photos
          </TabsTrigger>
          <TabsTrigger
            value="interlaced"
            className="text-sm md:text-lg"
            onClick={() => onViewChange("interlaced")}
          >
            Identify Interlaced Footage
          </TabsTrigger>
          <TabsTrigger
            value="compound"
            className="text-sm md:text-lg"
            onClick={() => onViewChange("compound")}
          >
            Identify Compound Clips
          </TabsTrigger>
        </TabsList>
      </Tabs>
    </>
  );
}
export default NavigationTabs;
