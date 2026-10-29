import { redirect } from "next/navigation";

export default function FeesIndexPage() {
    redirect("/dashboard/fees/collect");
}
