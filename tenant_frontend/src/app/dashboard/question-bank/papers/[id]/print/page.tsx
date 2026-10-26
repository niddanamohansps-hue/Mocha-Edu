"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { usePrintablePaper } from "@/hooks/useQuestionBank";
import { inventoryErrorMessage } from "@/hooks/useInventory";

const LETTERS = "ABCDEFGH";

/** The paper as it is printed, or (``?key=1``) its answer key. Opening either is logged on the server. */
export default function PrintPaperPage() {
    const { id } = useParams<{ id: string }>();
    const withAnswers = useSearchParams().get("key") === "1";
    const { data: paper, isLoading, isError, error } = usePrintablePaper(id, withAnswers);

    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !paper) return <ErrorState message={inventoryErrorMessage(error, "This paper cannot be opened yet.")} />;

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 print:hidden">
                <Link href={`/dashboard/question-bank/papers/${id}`} className="text-sky-700 hover:underline text-sm">Back to the paper</Link>
                {!paper.is_frozen && <span className="text-sm text-amber-700">Not approved yet: this is a working copy.</span>}
                <Button className="ml-auto" onClick={() => window.print()}>Print</Button>
            </div>
            <article className="mx-auto max-w-3xl bg-white text-black p-8 rounded-2xl border border-slate-200 print:border-0 print:p-0 space-y-6">
                <header className="text-center space-y-1 border-b border-slate-300 pb-4">
                    <p className="text-sm font-semibold uppercase tracking-wide">{paper.examination}</p>
                    <h1 className="text-xl font-bold">{paper.subject} · {paper.level}{withAnswers ? " · ANSWER KEY" : ""}</h1>
                    <p className="text-sm">Set {paper.set_label} · Time: {paper.duration_minutes} minutes · Maximum marks: {Number(paper.total_marks)}</p>
                </header>
                {paper.instructions && !withAnswers && <p className="text-sm whitespace-pre-wrap">{paper.instructions}</p>}
                {paper.sections.map((section) => (
                    <section key={section.title} className="space-y-3">
                        <h2 className="font-bold">{section.title}</h2>
                        {section.instructions && <p className="text-sm italic">{section.instructions}</p>}
                        <ol className="space-y-4">
                            {section.questions.map((q) => (
                                <li key={q.number} className="text-sm break-inside-avoid">
                                    <div className="flex gap-2">
                                        <span className="font-semibold">{q.number}.</span>
                                        <span className="flex-1 whitespace-pre-wrap">{q.body}</span>
                                        <span className="font-semibold">[{Number(q.marks)}]</span>
                                    </div>
                                    {q.options.length > 0 && (
                                        <ol className="pl-8 mt-1 space-y-0.5">
                                            {q.options.map((option, i) => (
                                                <li key={i} className={withAnswers && q.correct?.includes(i) ? "font-bold underline" : ""}>({LETTERS[i]}) {option}</li>
                                            ))}
                                        </ol>
                                    )}
                                    {withAnswers && (
                                        <div className="pl-8 mt-1 space-y-1 text-slate-700">
                                            {q.correct && q.correct.length > 0 && <p><b>Correct:</b> {q.correct.map((i) => LETTERS[i]).join(", ")}</p>}
                                            {q.answer && <p className="whitespace-pre-wrap"><b>Answer:</b> {q.answer}</p>}
                                            {q.marking_scheme && <p className="whitespace-pre-wrap"><b>Marking:</b> {q.marking_scheme}</p>}
                                        </div>
                                    )}
                                </li>
                            ))}
                        </ol>
                    </section>
                ))}
            </article>
        </div>
    );
}
