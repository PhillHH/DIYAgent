import type { ComponentType } from "react";
import { useMemo, useRef } from "react";
import { motion } from "framer-motion";
import { ClipboardList, Mail, Search, Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import clsx from "clsx";

import { startResearch } from "../api";

const formSchema = z.object({
  email: z.string().email({ message: "Bitte eine gültige E-Mail-Adresse eintragen." }),
  query: z
    .string()
    .min(10, "Bitte mindestens 10 Zeichen eingeben.")
    .max(2000, "Die Anfrage darf maximal 2000 Zeichen enthalten."),
});

type FormValues = z.infer<typeof formSchema>;

type LucideIcon = ComponentType<{ className?: string }>;

type Feature = {
  title: string;
  description: string;
  Icon: LucideIcon;
  accent: string;
};

type RequestCardProps = {
  /** True, solange ein Backend-Job aktiv ist – Formular wird dann deaktiviert. */
  isRunning: boolean;
  /** Wird unmittelbar vor dem Start einer neuen Anfrage aufgerufen (z. B. um alte Jobs abzubrechen). */
  onSubmitStart: () => void;
  /** Registriert den AbortController der laufenden Anfrage beim Parent. */
  onRegisterRequestController: (controller: AbortController | null) => void;
  /** Informiert den Parent über die neue Job-ID, damit Polling gestartet werden kann. */
  onStart: (jobId: string) => void;
  /** Liefert Fehlermeldungen an den Parent, falls der Start misslingt. */
  onError: (message: string) => void;
  /** Helper zum Übersetzen beliebiger Fehlerobjekte in nutzerfreundliche Texte. */
  extractErrorMessage: (error: unknown) => string;
};

const features: Feature[] = [
  {
    title: "Material & Einkauf",
    description: "Wir schlagen dir passende Bauhaus-Produkte samt kurzer Hinweise und Preisen vor – ohne stundenlange Recherche.",
    Icon: Search,
    accent: "from-emerald-200/60 via-emerald-100/40 to-transparent",
  },
  {
    title: "Planung Schritt für Schritt",
    description: "Home Task AI strukturiert dein Projekt in klare Schritte, Checklisten und Zeitblöcke – bereit zum Loslegen.",
    Icon: ClipboardList,
    accent: "from-amber-200/60 via-amber-100/40 to-transparent",
  },
  {
    title: "Report im Postfach",
    description: "Der komplette Projektplan kommt als übersichtliche E-Mail. So hast du alles griffbereit in der Werkstatt.",
    Icon: Mail,
    accent: "from-emerald-300/50 via-emerald-200/40 to-transparent",
  },
];

const containerVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
};

export function RequestCard({
  isRunning,
  onSubmitStart,
  onRegisterRequestController,
  onStart,
  onError,
  extractErrorMessage,
}: RequestCardProps): JSX.Element {
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: "", query: "" },
  });

  // Referenz auf den zuletzt genutzten AbortController, um Doppel-Registrierung zu verhindern.
  const localControllerRef = useRef<AbortController | null>(null);

  const queryLength = watch("query")?.length ?? 0;
  const queryHint = useMemo(() => `${queryLength} / 2000 Zeichen`, [queryLength]);

  const onSubmit = handleSubmit(async (values) => {
    onSubmitStart();
    const controller = new AbortController();
    localControllerRef.current = controller;
    onRegisterRequestController(controller);

    try {
      const response = await startResearch(values, controller.signal);
      reset(values); // merkt sich die Eingaben, damit Nutzer:innen nachjustieren können.
      onStart(response.job_id);
    } catch (error) {
      // Bei Abbruch (z. B. neuer Submit) schweigend beenden.
      if ((error instanceof DOMException && error.name === "AbortError") || (error as { code?: string })?.code === "ERR_CANCELED") {
        return;
      }
      onError(extractErrorMessage(error));
    } finally {
      if (localControllerRef.current === controller) {
        localControllerRef.current = null;
      }
      onRegisterRequestController(null);
    }
  });

  const disabled = isRunning || isSubmitting;

  return (
    <motion.section
      className="card-glass"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      transition={{ duration: 0.6, ease: "easeOut", delay: 0.1 }}
    >
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <motion.form
          className="space-y-5"
          onSubmit={onSubmit}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut", delay: 0.2 }}
        >
          <div className="space-y-2">
            <label htmlFor="email" className="block text-sm font-medium text-stone-700">
              E-Mail-Adresse
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-emerald-500" aria-hidden="true" />
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="dein.name@example.com"
                className="block w-full rounded-2xl border border-stone-200 bg-white pl-10 pr-4 py-3 text-base text-stone-800 shadow-sm placeholder:text-stone-400 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/40 focus:ring-offset-2 focus:ring-offset-amber-50 focus:outline-none"
                {...register("email")}
                disabled={disabled}
                aria-invalid={errors.email ? "true" : "false"}
                aria-describedby={errors.email ? "email-error" : undefined}
              />
            </div>
            {errors.email && (
              <span id="email-error" className="text-sm text-rose-500">
                {errors.email.message}
              </span>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label htmlFor="query" className="text-sm font-medium text-stone-700">
                Heimwerker-Anfrage
              </label>
              <span className="text-xs text-stone-400">{queryHint}</span>
            </div>
            <textarea
              id="query"
              rows={6}
              placeholder="Beschreibe dein Vorhaben – z. B. Garderobenschrank bauen, Maße, Wunschmaterial, Budget."
              className="block w-full resize-vertical rounded-2xl border border-stone-200 bg-white px-4 py-3 text-base text-stone-800 shadow-sm placeholder:text-stone-400 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/40 focus:ring-offset-2 focus:ring-offset-amber-50 focus:outline-none"
              {...register("query")}
              disabled={disabled}
              aria-invalid={errors.query ? "true" : "false"}
              aria-describedby={errors.query ? "query-error" : undefined}
            />
            {errors.query && (
              <span id="query-error" className="text-sm text-rose-500">
                {errors.query.message}
              </span>
            )}
          </div>

          <motion.button
            type="submit"
            className={clsx("btn-primary w-full sm:w-auto", disabled && "cursor-wait opacity-70")}
            disabled={disabled}
            whileHover={{ scale: disabled ? 1 : 1.02 }}
            whileTap={{ scale: disabled ? 1 : 0.99 }}
          >
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            {isSubmitting ? "Projekt wird vorbereitet…" : "Projekt-Report starten"}
          </motion.button>
        </motion.form>

        <motion.aside
          className="flex flex-col gap-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: "easeOut", delay: 0.25 }}
        >
          <h3 className="text-sm font-semibold uppercase tracking-wide text-stone-600">So unterstützt dich Home Task AI</h3>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            {features.map(({ title, description, Icon, accent }, index) => (
              <motion.div
                key={title}
                className="group relative overflow-hidden rounded-2xl border border-stone-200 bg-white p-4 text-left shadow-sm transition-all duration-300"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: "easeOut", delay: 0.25 + index * 0.08 }}
                whileHover={{ y: -4 }}
              >
                <div className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${accent} opacity-0 transition-opacity duration-300 group-hover:opacity-70`} />
                <div className="relative mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100">
                  <Icon className="h-5 w-5 text-emerald-600" aria-hidden="true" />
                </div>
                <h4 className="relative text-sm font-semibold text-stone-800">{title}</h4>
                <p className="relative mt-1 text-sm text-stone-600">{description}</p>
              </motion.div>
            ))}
          </div>
        </motion.aside>
      </div>
    </motion.section>
  );
}

export default RequestCard;
