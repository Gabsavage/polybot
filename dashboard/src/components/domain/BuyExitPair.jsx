import { CornerDownRight } from "lucide-react";
import AlertCard from "./AlertCard";
import ExitCard from "./ExitCard";

export default function BuyExitPair({ buy, exit }) {
  return (
    <div className="relative flex flex-col gap-2">
      <AlertCard alert={buy} />
      <div className="flex items-center gap-2 pl-4 text-text-tertiary">
        <CornerDownRight size={14} />
        <span className="h-px flex-1 bg-white/[0.06]" />
      </div>
      <ExitCard exit={exit} />
    </div>
  );
}
