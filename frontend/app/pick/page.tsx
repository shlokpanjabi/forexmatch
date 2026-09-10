import { Wizard } from "@/components/pick/Wizard";
import { Nav } from "@/components/site/Nav";

export const metadata = {
  title: "Find my card — ForexMatch",
  description: "Six questions, about a minute, and every eligible card ranked for your usage.",
};

export default function PickPage() {
  return (
    <>
      <Nav />
      <main>
        <Wizard />
      </main>
    </>
  );
}
