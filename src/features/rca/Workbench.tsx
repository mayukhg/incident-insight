import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  Braces,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  Clipboard,
  Clock3,
  Copy,
  Database,
  Download,
  FileCode2,
  GitCommitHorizontal,
  LoaderCircle,
  Play,
  Radar,
  RefreshCw,
  RouteIcon,
  SearchCode,
  ShieldCheck,
  TrendingUp,
  TriangleAlert,
  Zap,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { generatePolicyExport, runProbe, simulateRemediation, startInvestigation } from "./investigations.functions";
import { investigationQueryOptions, investigationsQueryOptions } from "./queries";
import type { EvidenceStatus, Scenario, SimulationView } from "./types";

const chartConfig = {
  baseline: { label: "Baseline auth", color: "var(--chart-baseline)" },
  incident: { label: "Incident auth", color: "var(--chart-incident)" },
  latency: { label: "Latency", color: "var(--chart-latency)" },
} satisfies ChartConfig;

const statusStyles: Record<EvidenceStatus, string> = {
  success: "border-positive/30 bg-positive/10 text-positive",
  anomaly: "border-negative/30 bg-negative/10 text-negative",
  inconclusive: "border-warning/30 bg-warning/10 text-warning",
};

function requiredAt<T>(items: T[], index: number): T {
  const item = items[index];
  if (item === undefined) throw new Error(`Missing item at index ${index}`);
  return item;
}

function copyText(text: string, label = "Copied to clipboard") {
  void navigator.clipboard.writeText(text);
  toast.success(label);
}

function syntaxLine(line: string, index: number) {
  const keywords = /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|WITH|AS|CASE|WHEN|THEN|ELSE|END|FILTER|AVG|COUNT|SUM|JOIN|ON|AND|BETWEEN|INTERVAL|HAVING|LIMIT|MIN)\b/gi;
  const parts = line.split(keywords);
  return (
    <div key={`${line}-${index}`} className="min-h-5 whitespace-pre">
      <span className="mr-4 inline-block w-5 select-none text-right text-quiet">{index + 1}</span>
      {parts.map((part, partIndex) =>
        keywords.test(part) ? (
          <span key={`${part}-${partIndex}`} className="text-code-keyword">{part}</span>
        ) : (
          <span key={`${part}-${partIndex}`}>{part}</span>
        ),
      )}
    </div>
  );
}

function PanelTitle({ eyebrow, title, action }: { eyebrow: string; title: string; action?: React.ReactNode }) {
  return (
    <div className="flex h-14 items-center justify-between border-b border-border px-4">
      <div>
        <p className="text-[10px] font-semibold uppercase text-muted-foreground">{eyebrow}</p>
        <h2 className="mt-0.5 text-sm font-semibold text-foreground">{title}</h2>
      </div>
      {action}
    </div>
  );
}

function StatusDot({ status }: { status: EvidenceStatus }) {
  if (status === "success") return <CheckCircle2 className="size-4 text-positive" />;
  if (status === "anomaly") return <TriangleAlert className="size-4 text-negative" />;
  return <CircleDot className="size-4 text-warning" />;
}

function InvestigationTree({ scenario, activeNode, onNodeChange }: { scenario: Scenario; activeNode: number; onNodeChange: (index: number) => void }) {
  return (
    <aside className="min-w-0 border-r border-border bg-panel">
      <PanelTitle eyebrow="Investigation" title="Hypothesis execution path" action={<Badge variant="outline" className="font-mono text-[10px] text-muted-foreground">4 QUERIES</Badge>} />
      <div className="px-3 py-4">
        {scenario.nodes.map((node, index) => (
          <div key={node.id} className="relative pb-3 last:pb-0">
            {index < scenario.nodes.length - 1 && <div className="absolute left-[18px] top-10 h-[calc(100%-24px)] w-px bg-border" />}
            <Button
              variant="ghost"
              onClick={() => onNodeChange(index)}
              className={cn(
                "relative h-auto w-full items-start justify-start whitespace-normal rounded-md border p-3 text-left shadow-none",
                activeNode === index
                  ? "border-active/50 bg-active/8 ring-1 ring-active/20 hover:bg-active/10"
                  : "border-transparent bg-transparent hover:border-border hover:bg-surface-raised",
              )}
            >
              <span className={cn("mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-md border bg-background font-mono text-[11px]", activeNode === index ? "border-active/50 text-active" : "border-border text-muted-foreground")}>
                {node.step}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 text-xs font-semibold text-foreground">
                  {node.title}
                  <StatusDot status={node.status} />
                </span>
                <span className="mt-1.5 block text-[11px] font-normal leading-4 text-muted-foreground">{node.finding}</span>
                <span className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[10px] font-normal text-quiet">
                  <span className="inline-flex items-center gap-1"><Clock3 className="size-3" />{node.runtime}</span>
                  <span>·</span><span>{node.rows}</span>
                </span>
              </span>
              <ChevronRight className={cn("mt-1 size-3.5", activeNode === index ? "text-active" : "text-quiet")} />
            </Button>
          </div>
        ))}
      </div>
      <div className="mx-3 mb-4 border-t border-border pt-4">
        <div className={cn("flex items-center gap-2 rounded-md border px-3 py-2.5", scenario.evidenceVerified ? "border-positive/20 bg-positive/5" : "border-warning/30 bg-warning/8")}>
          {scenario.evidenceVerified ? <ShieldCheck className="size-4 shrink-0 text-positive" /> : <AlertTriangle className="size-4 shrink-0 text-warning" />}
          <div>
            <p className="text-[11px] font-semibold text-foreground">{scenario.evidenceVerified ? "Proof execution gate passed" : scenario.stale ? "Evidence is stale" : "Evidence gate open"}</p>
            <p className="mt-0.5 text-[10px] text-muted-foreground">{scenario.evidenceVerified ? "Every claim maps to a completed query." : "Diagnosis waits for completed, current query evidence."}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}

function QueryEditor({ scenario, activeNode }: { scenario: Scenario; activeNode: number }) {
  const node = requiredAt(scenario.nodes, activeNode);
  return (
    <section className="border-b border-border">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-raised px-4 py-2">
        <div className="flex items-center gap-2">
          <FileCode2 className="size-3.5 text-active" />
          <span className="font-mono text-[11px] text-foreground">{node.id}_analysis.sql</span>
          <span className="text-[10px] text-muted-foreground">read only</span>
        </div>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-[11px] text-muted-foreground" onClick={() => copyText(node.sql, "SQL copied") }>
          <Copy className="size-3.5" /> Copy SQL
        </Button>
      </div>
      <div className="max-h-[228px] overflow-auto bg-code px-3 py-3 font-mono text-[11px] leading-5 text-code-foreground">
        {node.sql.split("\n").map(syntaxLine)}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border bg-surface-raised px-4 py-2 font-mono text-[10px] text-muted-foreground">
        {scenario.evidenceVerified ? <span className="inline-flex items-center gap-1.5 text-positive"><ShieldCheck className="size-3.5" /> ZERO SPECULATION VERIFIED</span> : <span className="inline-flex items-center gap-1.5 text-warning"><AlertTriangle className="size-3.5" /> EVIDENCE PENDING</span>}
        <span className="h-3 w-px bg-border" />
        <span>DUCKDB</span><span>·</span><span>{node.runtime}</span><span>·</span><span>{node.rows}</span>
      </div>
    </section>
  );
}

function VarianceTable({ scenario, activeNode }: { scenario: Scenario; activeNode: number }) {
  const rows = requiredAt(scenario.nodes, activeNode).cohorts;
  return (
    <section className="border-b border-border">
      <div className="flex items-center justify-between px-4 py-3">
        <div>
          <h3 className="text-xs font-semibold text-foreground">Cohort variance</h3>
          <p className="mt-0.5 text-[10px] text-muted-foreground">Shift-and-lift test against matched baseline</p>
        </div>
        <Badge variant="outline" className="font-mono text-[9px] text-muted-foreground">p &lt; 0.05 GATE</Badge>
      </div>
      <Table className="min-w-[690px] font-mono text-[10px]">
        <TableHeader>
          <TableRow className="border-border bg-surface-raised hover:bg-surface-raised">
            <TableHead className="h-8 pl-4 text-[9px] uppercase">Slice</TableHead>
            <TableHead className="h-8 text-right text-[9px] uppercase">Base vol</TableHead>
            <TableHead className="h-8 text-right text-[9px] uppercase">Base auth</TableHead>
            <TableHead className="h-8 text-right text-[9px] uppercase">Inc vol</TableHead>
            <TableHead className="h-8 text-right text-[9px] uppercase">Inc auth</TableHead>
            <TableHead className="h-8 text-right text-[9px] uppercase">Delta</TableHead>
            <TableHead className="h-8 pr-4 text-right text-[9px] uppercase">p-value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.slice} className="border-border hover:bg-surface-raised/70">
              <TableCell className="max-w-[180px] truncate py-2 pl-4 font-sans text-[11px] font-medium text-foreground">{row.slice}</TableCell>
              <TableCell className="py-2 text-right text-muted-foreground">{row.baselineVolume}</TableCell>
              <TableCell className="py-2 text-right text-muted-foreground">{row.baselineAuth ? `${row.baselineAuth.toFixed(1)}%` : "—"}</TableCell>
              <TableCell className="py-2 text-right text-muted-foreground">{row.incidentVolume}</TableCell>
              <TableCell className="py-2 text-right text-foreground">{row.incidentAuth ? `${row.incidentAuth.toFixed(1)}%` : "—"}</TableCell>
              <TableCell className={cn("py-2 text-right font-semibold", row.delta < -2 ? "text-negative" : row.delta > 0 ? "text-positive" : "text-muted-foreground")}>{row.delta ? `${row.delta > 0 ? "+" : ""}${row.delta.toFixed(1)}pp` : "—"}</TableCell>
              <TableCell className={cn("py-2 pr-4 text-right", row.pValue.includes("<") ? "text-positive" : "text-muted-foreground")}>{row.pValue}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

function TelemetryChart({ scenario, activeNode }: { scenario: Scenario; activeNode: number }) {
  return (
    <section className="px-4 py-4">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-xs font-semibold text-foreground">Auth rate & gateway latency</h3>
          <p className="mt-0.5 text-[10px] text-muted-foreground">{requiredAt(scenario.nodes, activeNode).chartLabel}</p>
        </div>
        <div className="flex items-center gap-3 text-[9px] text-muted-foreground">
          <span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-chart-baseline" />Baseline</span>
          <span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-chart-incident" />Incident</span>
          <span className="flex items-center gap-1.5"><i className="size-2 rounded-full bg-chart-latency" />Latency</span>
        </div>
      </div>
      <ChartContainer config={chartConfig} className="h-[220px] w-full aspect-auto">
        <LineChart data={scenario.chart} margin={{ top: 16, right: 6, left: -18, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="3 3" />
          <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={8} interval={1} />
          <YAxis yAxisId="auth" domain={[45, 95]} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} />
          <YAxis yAxisId="latency" orientation="right" domain={[0, 1600]} hide />
          <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
          <ReferenceLine yAxisId="auth" x={scenario.markerTime} stroke="var(--marker)" strokeDasharray="4 4" label={{ value: scenario.markerLabel, fill: "var(--marker)", fontSize: 9, position: "insideTopRight" }} />
          <Line yAxisId="auth" type="monotone" dataKey="baseline" stroke="var(--color-baseline)" strokeWidth={1.5} dot={false} />
          <Line yAxisId="auth" type="monotone" dataKey="incident" stroke="var(--color-incident)" strokeWidth={2} dot={false} />
          <Line yAxisId="latency" type="monotone" dataKey="latency" stroke="var(--color-latency)" strokeWidth={1.5} dot={false} strokeDasharray="3 3" />
        </LineChart>
      </ChartContainer>
    </section>
  );
}

function Verdict({ scenario }: { scenario: Scenario }) {
  return (
    <section className="border-b border-border p-4">
      <div className="flex items-start justify-between gap-3">
        <div className={cn("flex size-9 shrink-0 items-center justify-center rounded-md border", scenario.status === "mixed" ? "border-warning/30 bg-warning/10 text-warning" : "border-negative/30 bg-negative/10 text-negative")}>
          {scenario.status === "mixed" ? <AlertTriangle className="size-4" /> : <Radar className="size-4" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase text-muted-foreground">{scenario.status === "mixed" ? "Current classification" : "Isolated root cause"}</p>
          <h3 className="mt-1 text-sm font-semibold leading-5 text-foreground">{scenario.rootCause}</h3>
        </div>
      </div>
      <p className="mt-3 text-[11px] leading-5 text-muted-foreground">{scenario.summary}</p>
      <div className="mt-4 flex items-end justify-between">
        <div><span className="font-mono text-2xl font-semibold text-foreground">{scenario.confidence}%</span><span className="ml-2 text-[10px] uppercase text-muted-foreground">confidence</span></div>
        <span className="font-mono text-[9px] text-muted-foreground">{scenario.status === "mixed" ? "BELOW 80% GATE" : "4/4 TESTS PASSED"}</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"><div className={cn("h-full transition-all duration-500", scenario.status === "mixed" ? "bg-warning" : "bg-positive")} style={{ width: `${scenario.confidence}%` }} /></div>
    </section>
  );
}

function ImpactMetrics({ scenario }: { scenario: Scenario }) {
  const items = [
    { label: "GTV loss", value: scenario.gtvRisk, icon: ArrowDownRight, tone: "text-negative" },
    { label: "Impacted", value: scenario.lostTransactions, icon: Activity, tone: "text-foreground" },
    { label: "Abandonment", value: scenario.customerAbandonment, icon: TrendingUp, tone: "text-warning" },
  ];
  return (
    <section className="grid grid-cols-3 border-b border-border">
      {items.map((item, index) => <div key={item.label} className={cn("min-w-0 px-3 py-3", index < items.length - 1 && "border-r border-border")}><div className="flex items-center gap-1.5 text-[9px] uppercase text-muted-foreground"><item.icon className="size-3" />{item.label}</div><p className={cn("mt-1.5 truncate font-mono text-xs font-semibold", item.tone)}>{item.value}</p></div>)}
    </section>
  );
}

function Remediation({ scenario, simulated, onSimulate, simulating, openExport, projectedAuth, recoveredGtv }: { scenario: Scenario; simulated: boolean; onSimulate: (value: boolean) => void; simulating: boolean; openExport: () => void; projectedAuth?: number; recoveredGtv?: string }) {
  return (
    <section className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div><h3 className="text-xs font-semibold text-foreground">Remediation sandbox</h3><p className="mt-0.5 text-[10px] text-muted-foreground">What-if model · no production writes</p></div>
        <Switch checked={simulated} onCheckedChange={onSimulate} disabled={simulating} aria-label="Simulate dynamic routing failover" className="data-[state=checked]:bg-positive" />
      </div>
      <div className={cn("mt-3 rounded-md border p-3 transition-colors", simulated ? "border-positive/30 bg-positive/5" : "border-border bg-surface-raised")}>
        <div className="flex items-center gap-2"><RouteIcon className={cn("size-4", simulated ? "text-positive" : "text-muted-foreground")} /><span className="text-[10px] font-semibold uppercase text-muted-foreground">Target rule</span></div>
        <p className="mt-2 text-xs font-medium leading-5 text-foreground">{scenario.targetRule}</p>
        <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
          <div><p className="text-[9px] uppercase text-muted-foreground">Projected auth</p><p className={cn("mt-1 font-mono text-lg font-semibold", simulated ? "text-positive" : "text-foreground")}>{simulated ? `${(projectedAuth ?? scenario.incidentAuth).toFixed(1)}%` : `${scenario.incidentAuth.toFixed(1)}%`}</p></div>
          <ArrowRight className="size-4 text-muted-foreground" />
          <div className="text-right"><p className="text-[9px] uppercase text-muted-foreground">Recovered GTV</p><p className={cn("mt-1 font-mono text-lg font-semibold", simulated ? "text-positive" : "text-muted-foreground")}>{simulated ? recoveredGtv ?? "$0/hr" : "$0/hr"}</p></div>
        </div>
      </div>
      {simulated && <div className="mt-3 flex items-start gap-2 rounded-md border border-positive/20 bg-positive/8 px-3 py-2.5"><Zap className="mt-0.5 size-3.5 shrink-0 text-positive" /><p className="text-[10px] leading-4 text-positive">Simulation recovers modeled loss with sufficient target-gateway capacity. No production writes.</p></div>}
      <Button className="mt-3 w-full bg-active text-active-foreground hover:bg-active/90" disabled={!simulated} onClick={openExport}><Braces className="size-4" />Export routing policy</Button>
    </section>
  );
}

function MixedEvidence({ scenario, onProbe }: { scenario: Scenario; onProbe: (probeId: string, title: string) => void }) {
  return (
    <section className="p-4">
      <div className="rounded-md border border-warning/30 bg-warning/8 p-3">
        <div className="flex items-center gap-2 text-warning"><AlertTriangle className="size-4" /><h3 className="text-xs font-semibold">Ambiguity diagnostic</h3></div>
        <p className="mt-2 text-[10px] leading-4 text-muted-foreground">Remediation is blocked. Available evidence does not support a safe routing change.</p>
      </div>
      <div className="mt-4">
        <h3 className="text-[10px] font-semibold uppercase text-muted-foreground">Counter-evidence ledger</h3>
        <div className="mt-2 divide-y divide-border border-y border-border">
          {scenario.counterEvidence?.map((item) => <div key={item} className="flex gap-2 py-2.5"><CircleDot className="mt-0.5 size-3.5 shrink-0 text-warning" /><p className="text-[10px] leading-4 text-foreground">{item}</p></div>)}
        </div>
      </div>
      <div className="mt-4">
        <h3 className="text-[10px] font-semibold uppercase text-muted-foreground">Recommended probes</h3>
        <div className="mt-2 space-y-2">
          {scenario.probes?.map((probe) => <Button key={probe.probeId} variant="outline" onClick={() => onProbe(probe.probeId, probe.title)} className="h-auto w-full justify-start whitespace-normal border-border bg-surface-raised p-3 text-left"><SearchCode className="mt-0.5 size-4 shrink-0 text-active" /><span><span className="block text-[11px] font-semibold text-foreground">{probe.title}</span><span className="mt-0.5 block text-[10px] font-normal text-muted-foreground">{probe.description}</span></span></Button>)}
        </div>
      </div>
    </section>
  );
}

function ExportDialog({ open, onOpenChange, scenario, simulation }: { open: boolean; onOpenChange: (value: boolean) => void; scenario: Scenario; simulation: SimulationView | null }) {
  const [format, setFormat] = useState("json");
  const json = simulation?.json ?? "{}";
  const terraform = simulation?.terraform ?? "";
  const code = format === "json" ? json : terraform;
  const download = () => {
    const blob = new Blob([code], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `routing-policy.${format === "json" ? "json" : "tf"}`; anchor.click(); URL.revokeObjectURL(url);
  };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-w-2xl border-border bg-panel p-0 text-foreground"><DialogHeader className="border-b border-border px-5 py-4"><DialogTitle className="flex items-center gap-2 text-sm"><FileCode2 className="size-4 text-active" />Export routing policy</DialogTitle><DialogDescription className="text-[11px]">Generated from the verified {scenario.rootCause} remediation simulation.{simulation?.evidenceHash ? ` Evidence ${simulation.evidenceHash.slice(0, 12)}.` : ""}</DialogDescription></DialogHeader><div className="px-5 pb-5"><Tabs value={format} onValueChange={setFormat}><TabsList className="mt-4 h-8 rounded-md bg-muted p-0.5"><TabsTrigger value="json" className="h-7 rounded-sm px-4 text-[11px]">JSON</TabsTrigger><TabsTrigger value="terraform" className="h-7 rounded-sm px-4 text-[11px]">Terraform</TabsTrigger></TabsList><TabsContent value={format} className="mt-3"><pre className="max-h-80 overflow-auto rounded-md border border-border bg-code p-4 font-mono text-[11px] leading-5 text-code-foreground">{code}</pre></TabsContent></Tabs><div className="mt-4 flex justify-end gap-2"><Button variant="outline" size="sm" onClick={() => copyText(code, "Policy copied")}><Clipboard className="size-3.5" />Copy</Button><Button size="sm" className="bg-active text-active-foreground hover:bg-active/90" onClick={download}><Download className="size-3.5" />Download</Button></div></div></DialogContent></Dialog>;
}

export function Workbench() {
  const queryClient = useQueryClient();
  const listQuery = useQuery(investigationsQueryOptions);
  const [scenarioId, setScenarioId] = useState("scenario_a");
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [simulated, setSimulated] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [simulation, setSimulation] = useState<SimulationView | null>(null);
  const detailQuery = useQuery({
    ...investigationQueryOptions(scenarioId),
    enabled: Boolean(scenarioId) && listQuery.isSuccess,
  });
  const scenario = detailQuery.data;
  const summaries = listQuery.data ?? [];

  useEffect(() => {
    const first = summaries[0]?.id;
    if (first && !summaries.some((item) => item.id === scenarioId)) {
      setScenarioId(first);
    }
  }, [summaries, scenarioId]);

  useEffect(() => {
    if (!scenario) return;
    const existing = scenario.nodes.find((node) => node.id === activeNodeId);
    if (existing) return;
    const preferred = scenario.status === "mixed" ? scenario.nodes[1] : scenario.nodes[scenario.nodes.length - 1];
    setActiveNodeId(preferred?.id ?? scenario.nodes[0]?.id ?? null);
  }, [scenario, activeNodeId]);

  const activeNode = useMemo(() => {
    if (!scenario) return 0;
    const index = scenario.nodes.findIndex((node) => node.id === activeNodeId);
    return index >= 0 ? index : 0;
  }, [scenario, activeNodeId]);

  const displayedAuth = (simulated && simulation ? simulation.projectedAuth : scenario?.incidentAuth) ?? 0;
  const displayedDelta = simulated && simulation && scenario ? displayedAuth - scenario.incidentAuth : scenario?.delta ?? 0;

  const rerunMutation = useMutation({
    mutationFn: () => startInvestigation({ data: { investigationId: scenarioId } }),
    onMutate: () => {
      setSimulated(false);
      setSimulation(null);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["investigations", scenarioId] });
      toast.success("Investigation complete", { description: "Hypothesis steps re-executed against the DuckDB ledger." });
    },
    onError: (error: Error) => toast.error("Re-run failed", { description: error.message }),
  });
  const simulateMutation = useMutation({
    mutationFn: () => simulateRemediation({ data: { investigationId: scenarioId, ...(scenario?.proposalId ? { proposalId: scenario.proposalId } : {}) } }),
    onSuccess: (result) => {
      setSimulation(result);
      setSimulated(true);
      toast.success("Failover simulated", { description: "No production routing writes were issued." });
    },
    onError: (error: Error) => {
      setSimulated(false);
      toast.error("Simulation blocked", { description: error.message });
    },
  });
  const probeMutation = useMutation({
    mutationFn: (probeId: string) => runProbe({ data: { investigationId: scenarioId, probeId } }),
    onSuccess: async (_result, probeId) => {
      await queryClient.invalidateQueries({ queryKey: ["investigations", scenarioId] });
      toast.success("Probe executed", { description: `${probeId} completed against allowlisted SQL.` });
    },
    onError: (error: Error) => toast.error("Probe failed", { description: error.message }),
  });
  const exportMutation = useMutation({
    mutationFn: (format: "json" | "terraform") => {
      if (!scenario?.proposalId) throw new Error("No verified proposal");
      return generatePolicyExport({ data: { investigationId: scenarioId, proposalId: scenario.proposalId, format } });
    },
    onSuccess: (result) => setSimulation(result),
  });

  const changeScenario = (id: string) => {
    setScenarioId(id);
    setActiveNodeId(null);
    setSimulated(false);
    setSimulation(null);
  };
  const rerunning = rerunMutation.isPending || (detailQuery.isFetching && !detailQuery.data);
  const onSimulate = (value: boolean) => {
    if (!value) {
      setSimulated(false);
      return;
    }
    simulateMutation.mutate();
  };
  const handleProbe = (probeId: string, title: string) => {
    toast.info("Running probe", { description: title });
    probeMutation.mutate(probeId);
  };
  const openExport = () => {
    if (simulation) {
      setExportOpen(true);
      if (scenario?.proposalId) exportMutation.mutate("json");
    }
  };

  if (listQuery.isError || detailQuery.isError) {
    const message = (listQuery.error as Error | undefined)?.message ?? (detailQuery.error as Error | undefined)?.message ?? "Analytical service unavailable";
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
        <div className="max-w-md text-center">
          <h1 className="text-lg font-semibold">Investigation service unavailable</h1>
          <p className="mt-2 text-sm text-muted-foreground">{message}</p>
          <Button className="mt-4" onClick={() => { void listQuery.refetch(); void detailQuery.refetch(); }}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!scenario) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Loading DuckDB investigation…
      </div>
    );
  }

  const recoveredDisplay = simulated && simulation ? simulation.recoveredGtv : scenario.recoveredGtv;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
        <div className="flex min-h-14 flex-wrap items-center gap-3 px-4 py-2 xl:flex-nowrap">
          <div className="flex shrink-0 items-center gap-2.5 pr-3 xl:border-r xl:border-border">
            <div className="flex size-8 items-center justify-center rounded-md border border-active/30 bg-active/10 text-active"><Activity className="size-4" /></div>
            <div><p className="text-[10px] font-semibold uppercase text-muted-foreground">Payment Ops</p><h1 className="text-xs font-semibold text-foreground">RCA Workbench</h1></div>
          </div>
          <Select value={scenarioId} onValueChange={changeScenario}>
            <SelectTrigger className="h-9 min-w-0 flex-1 border-border bg-panel text-xs shadow-none xl:max-w-[480px]"><SelectValue /></SelectTrigger>
            <SelectContent className="border-border bg-popover">
              {summaries.map((item) => (
                <SelectItem key={item.id} value={item.id}>{item.shortName}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Badge variant="outline" className={cn("h-7 gap-1.5 px-2.5 text-[9px] font-semibold uppercase", rerunning ? "border-active/30 bg-active/10 text-active" : scenario.status === "mixed" ? "border-warning/30 bg-warning/10 text-warning" : "border-positive/30 bg-positive/10 text-positive")}>
            {rerunning ? <LoaderCircle className="size-3 animate-spin" /> : scenario.status === "mixed" ? <AlertTriangle className="size-3" /> : <ShieldCheck className="size-3" />}
            {rerunning ? "Analyzing" : scenario.status === "mixed" ? "Mixed evidence" : "Definitive RCA"}
          </Badge>
          <Button variant="outline" size="sm" onClick={() => rerunMutation.mutate()} disabled={rerunning} className="ml-auto h-8 border-border bg-panel text-[11px]"><RefreshCw className={cn("size-3.5", rerunning && "animate-spin")} />Re-run investigation</Button>
        </div>
        <div className="grid grid-cols-2 border-t border-border sm:grid-cols-4 xl:absolute xl:left-[580px] xl:top-0 xl:h-14 xl:w-[calc(100%-780px)] xl:border-l xl:border-t-0">
          {[{ label: "Baseline auth", value: `${scenario.baselineAuth.toFixed(1)}%`, sub: "matched window" }, { label: simulated ? "Simulated auth" : "Incident auth", value: `${displayedAuth.toFixed(1)}%`, sub: simulated ? "failover model" : scenario.window }, { label: simulated ? "Projected lift" : "Variance", value: `${displayedDelta > 0 ? "+" : ""}${displayedDelta.toFixed(1)}%`, sub: simulated ? "vs incident" : "vs baseline" }, { label: simulated ? "GTV recovered" : "GTV at risk", value: simulated ? recoveredDisplay ?? "$0/hr" : scenario.gtvRisk, sub: simulated ? "per hour" : "modeled exposure" }].map((kpi, index) => <div key={kpi.label} className={cn("min-w-0 border-border px-3 py-2", index > 0 && "border-l", index > 1 && "border-t sm:border-t-0")}><p className="text-[8px] font-semibold uppercase text-muted-foreground">{kpi.label}</p><div className="mt-0.5 flex min-w-0 items-baseline gap-1.5"><span className={cn("font-mono text-sm font-semibold", (index === 2 || index === 3) && (simulated ? "text-positive" : "text-negative"))}>{kpi.value}</span><span className="truncate text-[8px] text-quiet">{kpi.sub}</span></div></div>)}
        </div>
      </header>

      <main>
        <div className="border-b border-border bg-panel px-4 py-2 xl:hidden"><p className="truncate text-xs font-medium">{scenario.title}</p><p className="mt-0.5 text-[10px] text-muted-foreground">{scenario.window}</p></div>
        <div className="hidden min-h-[calc(100vh-57px)] grid-cols-[25%_48%_27%] xl:grid">
          <InvestigationTree scenario={scenario} activeNode={activeNode} onNodeChange={(index) => setActiveNodeId(requiredAt(scenario.nodes, index).id)} />
          <section className="min-w-0 border-r border-border bg-panel">
            <PanelTitle eyebrow="Proof workbench" title={requiredAt(scenario.nodes, activeNode).title} action={<div className="hidden items-center gap-1.5 text-[10px] text-muted-foreground 2xl:flex"><Database className="size-3" />synthetic_ledger.duckdb</div>} />
            <QueryEditor scenario={scenario} activeNode={activeNode} />
            <VarianceTable scenario={scenario} activeNode={activeNode} />
            <TelemetryChart scenario={scenario} activeNode={activeNode} />
          </section>
          <aside className="min-w-0 bg-panel">
            <PanelTitle eyebrow="RCA & action" title={scenario.status === "mixed" ? "Evidence review" : "Verdict & remediation"} action={<GitCommitHorizontal className="size-4 text-muted-foreground" />} />
            <Verdict scenario={scenario} /><ImpactMetrics scenario={scenario} />
            {scenario.status === "mixed" ? <MixedEvidence scenario={scenario} onProbe={handleProbe} /> : <Remediation scenario={scenario} simulated={simulated} onSimulate={onSimulate} simulating={simulateMutation.isPending} openExport={openExport} {...(simulation ? { projectedAuth: simulation.projectedAuth, recoveredGtv: simulation.recoveredGtv } : {})} />}
          </aside>
        </div>
        <Tabs defaultValue="evidence" className="xl:hidden">
          <TabsList className="sticky top-[122px] z-30 grid h-10 w-full grid-cols-3 rounded-none border-b border-border bg-background p-0"><TabsTrigger value="tree" className="h-10 rounded-none text-[11px]">Investigation</TabsTrigger><TabsTrigger value="evidence" className="h-10 rounded-none text-[11px]">Evidence</TabsTrigger><TabsTrigger value="verdict" className="h-10 rounded-none text-[11px]">Verdict</TabsTrigger></TabsList>
          <TabsContent value="tree" className="m-0"><InvestigationTree scenario={scenario} activeNode={activeNode} onNodeChange={(index) => setActiveNodeId(requiredAt(scenario.nodes, index).id)} /></TabsContent>
          <TabsContent value="evidence" className="m-0 bg-panel"><PanelTitle eyebrow="Proof workbench" title={requiredAt(scenario.nodes, activeNode).title} /><QueryEditor scenario={scenario} activeNode={activeNode} /><VarianceTable scenario={scenario} activeNode={activeNode} /><TelemetryChart scenario={scenario} activeNode={activeNode} /></TabsContent>
          <TabsContent value="verdict" className="m-0 bg-panel"><PanelTitle eyebrow="RCA & action" title={scenario.status === "mixed" ? "Evidence review" : "Verdict & remediation"} /><Verdict scenario={scenario} /><ImpactMetrics scenario={scenario} />{scenario.status === "mixed" ? <MixedEvidence scenario={scenario} onProbe={handleProbe} /> : <Remediation scenario={scenario} simulated={simulated} onSimulate={onSimulate} simulating={simulateMutation.isPending} openExport={openExport} {...(simulation ? { projectedAuth: simulation.projectedAuth, recoveredGtv: simulation.recoveredGtv } : {})} />}</TabsContent>
        </Tabs>
      </main>
      <ExportDialog open={exportOpen} onOpenChange={setExportOpen} scenario={scenario} simulation={simulation} />
    </div>
  );
}
