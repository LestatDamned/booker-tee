import { SessionPage } from "../session/session-page";

export function meta() {
  return [
    { title: "Booker Tee" },
    { name: "description", content: "Financial workbench" },
  ];
}

export default function Home() {
  return <SessionPage />;
}
