"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FormDialog, SELECT_CLASS } from "@/components/dashboard/question-bank/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useChapters, useMyScope, useSaveQuestion } from "@/hooks/useQuestionBank";
import {
    CHOICE_TYPES, DIFFICULTY_LABELS, Difficulty, Question, QuestionOption, QuestionType, TYPE_LABELS,
} from "@/types/QuestionBank";

const TEXTAREA_CLASS =
    "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm min-h-[88px]";

/** `question` undefined = closed, null = a new one, otherwise editing it. */
export function QuestionEditor({ question, onClose }: { question: Question | null | undefined; onClose: () => void }) {
    return question === undefined ? null : <EditorForm key={question?.id ?? "new"} question={question} onClose={onClose} />;
}

function defaultOptions(type: QuestionType): QuestionOption[] {
    if (type === "true_false") return [{ text: "True", is_correct: true }, { text: "False", is_correct: false }];
    if (type === "mcq" || type === "multi_select") return [{ text: "", is_correct: true }, { text: "", is_correct: false }, { text: "", is_correct: false }, { text: "", is_correct: false }];
    return [];
}

function EditorForm({ question, onClose }: { question: Question | null; onClose: () => void }) {
    const save = useSaveQuestion();
    const scope = useMyScope();
    const [subject, setSubject] = useState(question?.subject ?? "");
    const [chapter, setChapter] = useState(question?.chapter ?? "");
    const [topic, setTopic] = useState(question?.topic ?? "");
    const [type, setType] = useState<QuestionType>(question?.question_type ?? "mcq");
    const [difficulty, setDifficulty] = useState<Difficulty>(question?.difficulty ?? "medium");
    const [marks, setMarks] = useState(question ? String(Number(question.marks)) : "1");
    const [body, setBody] = useState(question?.body ?? "");
    const [options, setOptions] = useState<QuestionOption[]>(question?.options.length ? question.options : defaultOptions(question?.question_type ?? "mcq"));
    const [answer, setAnswer] = useState(question?.answer ?? "");
    const [explanation, setExplanation] = useState(question?.explanation ?? "");
    const [scheme, setScheme] = useState(question?.marking_scheme ?? "");
    const [outcome, setOutcome] = useState(question?.learning_outcome ?? "");
    const [error, setError] = useState<string | null>(null);
    const chapters = useChapters(subject);
    const topics = (chapters.data ?? []).find((c) => c.id === chapter)?.topics ?? [];
    const isChoice = CHOICE_TYPES.includes(type);

    const changeType = (next: QuestionType) => {
        setType(next);
        setOptions(defaultOptions(next));
    };
    const setOption = (index: number, patch: Partial<QuestionOption>) =>
        setOptions((current) => current.map((o, i) => {
            if (i === index) return { ...o, ...patch };
            // A single-answer question has one correct option: marking one unmarks the rest.
            if (patch.is_correct && (type === "mcq" || type === "true_false")) return { ...o, is_correct: false };
            return o;
        }));

    return (
        <FormDialog
            open
            wide
            onOpenChange={(open) => !open && onClose()}
            title={question ? `Edit question (version ${question.version})` : "New question"}
            description="Saved as a draft. Submit it for review when it is ready; a reviewer for the subject approves it."
            submitLabel={question ? "Save changes" : "Save draft"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                if (!subject) return setError("Choose the subject.");
                if (!body.trim()) return setError("Write the question.");
                if (!/^\d+(\.5|\.0)?$/.test(marks.trim()) || Number(marks) <= 0) return setError("Marks must be more than 0, in steps of 0.5.");
                if (isChoice && options.some((o) => !o.text.trim())) return setError("Fill in every option, or remove the empty ones.");
                if (!isChoice && !answer.trim()) return setError("Give the expected answer.");
                setError(null);
                save.mutate(
                    {
                        id: question?.id,
                        input: {
                            ...(question ? {} : { subject }), chapter: chapter || null, topic: topic || null, question_type: type,
                            difficulty, marks: marks.trim(), body: body.trim(), options: isChoice ? options.map((o) => ({ ...o, text: o.text.trim() })) : [],
                            answer: answer.trim(), explanation: explanation.trim(), marking_scheme: scheme.trim(), learning_outcome: outcome.trim(),
                        },
                    },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the question")) }
                );
            }}
        >
            <div className="grid sm:grid-cols-2 gap-3">
                <Field label="Subject" htmlFor="q-subject" hint={question ? "A question stays in its subject." : undefined}>
                    <select id="q-subject" className={SELECT_CLASS} value={subject} disabled={!!question} onChange={(e) => { setSubject(e.target.value); setChapter(""); setTopic(""); }}>
                        <option value="">Choose a subject</option>
                        {question && <option value={question.subject}>{question.subject_name} ({question.level_name})</option>}
                        {!question && (scope.data?.can_write ?? []).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.level_name})</option>)}
                    </select>
                </Field>
                <Field label="Question type" htmlFor="q-type">
                    <select id="q-type" className={SELECT_CLASS} value={type} onChange={(e) => changeType(e.target.value as QuestionType)}>
                        {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
                    </select>
                </Field>
                <Field label="Chapter (optional)" htmlFor="q-chapter">
                    <select id="q-chapter" className={SELECT_CLASS} value={chapter} disabled={!subject} onChange={(e) => { setChapter(e.target.value); setTopic(""); }}>
                        <option value="">No chapter</option>
                        {(chapters.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.order}. {c.name}</option>)}
                    </select>
                </Field>
                <Field label="Topic (optional)" htmlFor="q-topic">
                    <select id="q-topic" className={SELECT_CLASS} value={topic} disabled={!chapter} onChange={(e) => setTopic(e.target.value)}>
                        <option value="">No topic</option>
                        {topics.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                </Field>
                <Field label="Difficulty" htmlFor="q-diff">
                    <select id="q-diff" className={SELECT_CLASS} value={difficulty} onChange={(e) => setDifficulty(e.target.value as Difficulty)}>
                        {(Object.keys(DIFFICULTY_LABELS) as Difficulty[]).map((d) => <option key={d} value={d}>{DIFFICULTY_LABELS[d]}</option>)}
                    </select>
                </Field>
                <Field label="Marks" htmlFor="q-marks"><Input id="q-marks" inputMode="decimal" value={marks} onChange={(e) => setMarks(e.target.value)} /></Field>
            </div>

            <Field label="Question" htmlFor="q-body">
                <textarea id="q-body" className={TEXTAREA_CLASS} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />
            </Field>

            {isChoice && (
                <fieldset className="space-y-2">
                    <legend className="text-sm font-medium">Options <span className="font-normal text-slate-500">(tick the correct {type === "multi_select" ? "ones" : "one"})</span></legend>
                    {options.map((option, index) => (
                        <div key={index} className="flex items-center gap-2">
                            <input
                                type={type === "multi_select" ? "checkbox" : "radio"}
                                name="q-correct"
                                aria-label={`Option ${index + 1} is correct`}
                                checked={option.is_correct}
                                onChange={(e) => setOption(index, { is_correct: type === "multi_select" ? e.target.checked : true })}
                            />
                            <Input aria-label={`Option ${index + 1}`} value={option.text} maxLength={500} disabled={type === "true_false"} onChange={(e) => setOption(index, { text: e.target.value })} />
                            {type !== "true_false" && options.length > 2 && (
                                <Button type="button" size="sm" variant="ghost" onClick={() => setOptions(options.filter((_, i) => i !== index))}>Remove</Button>
                            )}
                        </div>
                    ))}
                    {type !== "true_false" && options.length < 8 && (
                        <Button type="button" size="sm" variant="outline" onClick={() => setOptions([...options, { text: "", is_correct: false }])}>Add option</Button>
                    )}
                </fieldset>
            )}

            <Field label={isChoice ? "Answer note (optional)" : "Expected answer"} htmlFor="q-answer">
                <textarea id="q-answer" className={TEXTAREA_CLASS} maxLength={5000} value={answer} onChange={(e) => setAnswer(e.target.value)} />
            </Field>
            {!isChoice && (
                <Field label="Marking scheme (optional)" htmlFor="q-scheme" hint="How the marks are given, for whoever marks the paper.">
                    <textarea id="q-scheme" className={TEXTAREA_CLASS} maxLength={5000} value={scheme} onChange={(e) => setScheme(e.target.value)} />
                </Field>
            )}
            <Field label="Explanation (optional)" htmlFor="q-expl">
                <textarea id="q-expl" className={TEXTAREA_CLASS} maxLength={5000} value={explanation} onChange={(e) => setExplanation(e.target.value)} />
            </Field>
            <Field label="Learning outcome (optional)" htmlFor="q-outcome">
                <Input id="q-outcome" maxLength={255} value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="e.g. Adds two-digit numbers" />
            </Field>
        </FormDialog>
    );
}
