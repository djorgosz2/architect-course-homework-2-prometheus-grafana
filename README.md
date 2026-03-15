# Monitoring & Alerting rendszer - Házi feladat

## Architektúra

```
┌─────────────────┐     scrape :9464     ┌────────────────┐
│  myapp-backend   │◄────────────────────│   Prometheus    │
│  (FastAPI+OTel)  │                     │   :9090         │
└─────────────────┘                     │                 │
                                         │  alerts.yml ──►│──► Alertmanager :9093
┌─────────────────┐     scrape :8080     │                 │
│    cAdvisor      │◄────────────────────│                 │
│ (container metrics)                    └────────┬───────┘
└─────────────────┘                              │
                                                  │ datasource
┌─────────────────┐     scrape :9100              ▼
│  Node Exporter   │◄────────────────    ┌────────────────┐
│ (host metrics)   │                     │    Grafana      │
└─────────────────┘                     │    :3000        │
                                         └────────────────┘
┌─────────────────┐
│ Load Generator   │──► HTTP traffic ──► myapp-backend
│ (curl loop)      │
└─────────────────┘
```

## Gyors indítás

```bash
docker compose up -d --build
```

| Service       | URL                         | Credentials    |
|---------------|-----------------------------|----------------|
| Grafana       | http://localhost:3000        | admin / admin  |
| Prometheus    | http://localhost:9090        | -              |
| Alertmanager  | http://localhost:9093        | -              |
| Application   | http://localhost:8000/docs   | -              |
| App Metrics   | http://localhost:9464        | -              |

A load generator automatikusan indul és forgalmat generál, így a dashboardon pár perc után láthatóak lesznek a metrikák.

## Metrikagyűjtés

### Alkalmazás metrikák (OpenTelemetry + Prometheus exporter, port 9464)
- `http_server_request_duration_seconds` - HTTP RED metrikák (auto-instrumentation)
- `myapp_operations_total` - Üzleti műveletek számláló (success/error)
- `myapp_request_processing_duration_seconds` - Feldolgozási idő
- `myapp_external_api_duration_seconds` - Külső API hívások ideje
- `myapp_db_connections_active` - Aktív DB kapcsolatok száma

### Infrastruktúra metrikák
- **cAdvisor** (port 8080): `container_memory_usage_bytes`, `container_cpu_usage_seconds_total`, `container_spec_memory_limit_bytes`
- **Node Exporter** (port 9100): `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `node_filesystem_avail_bytes`

## Dashboard panelek (Application Overview)

| #  | Panel                              | Metrika típus        | Cél                                           |
|----|------------------------------------|----------------------|-----------------------------------------------|
| 1  | HTTP Request Rate by Status Code   | RED - Rate           | Forgalom összképe státusz kódonként           |
| 2  | HTTP Error Rate                    | RED - Errors         | 4xx+5xx arány, 5%-os alert küszöb jelzésével  |
| 3  | HTTP Request Duration (Latency)    | RED - Duration       | p50, p95, p99 percentilisek + átlag           |
| 4  | Business Operations by Status      | App-specifikus       | Üzleti műveletek success/error bontásban      |
| 5  | Container Memory Usage / Limit     | Infrastruktúra       | Memória használatot a limithez mérik (80% alert) |
| 6  | Container CPU Usage                | Infrastruktúra       | CPU használat konténerenként                  |
| 7  | Disk Usage                         | Infrastruktúra       | Host szintű lemezhasználat                    |

Kiegészítő stat panelek: Application Status (up/down), Current Request Rate, Current Error Rate, P95 Latency,
Node Memory Usage, Node CPU Usage.

## Alerting szabályok

| Alert                    | Feltétel                                      | Severity | For   |
|--------------------------|-----------------------------------------------|----------|-------|
| HighHttpErrorRate        | HTTP error rate > 5%                          | critical | 5m    |
| HighHttpLatency          | p95 latency > 2s                              | warning  | 5m    |
| ApplicationDown          | `up{job="myapp-backend"} == 0`                | critical | 1m    |
| HighOperationErrorRate   | Business op error rate > 10%                  | warning  | 5m    |
| SlowExternalApiCalls     | External API p95 > 5s                         | warning  | 5m    |
| HighContainerMemoryUsage | Container memory > 80% limit                  | warning  | 5m    |
| HighContainerCpuUsage    | Container CPU > 75% limit (sustained 30s)     | warning  | 30s   |
| HighDiskUsage            | Disk usage > 85%                              | warning  | 10m   |
| HighNodeMemoryUsage      | Node memory > 85%                             | warning  | 5m    |

Az alertek az Alertmanager UI-ban láthatóak (http://localhost:9093), és a Grafana-ban is megjelennek.
Éles környezetben az `alertmanager.yml`-ben konfigurálható Slack / Email / PagerDuty értesítés.

## Leállítás

```bash
docker compose down          # konténerek leállítása (adatok megmaradnak)
docker compose down -v       # konténerek + volume-ok törlése
```

## Kapcsolódás Kubernetes-hez

Ez a Docker Compose setup a következő K8s komponenseket szimulálja:
- **cAdvisor** → kubelet beépített container metrics
- **Node Exporter** → node-exporter DaemonSet
- **Prometheus scrape annotations** → `prometheus.io/scrape: "true"` pod annotációk
- **Alertmanager** → kube-prometheus-stack AlertManager
- **Grafana provisioning** → ConfigMap-alapú dashboard deploy (`grafana_dashboard: "1"` label)

Éles K8s környezetben a metrikák automatikusan elérhetőek a kube-prometheus-stack-en keresztül,
a dashboard JSON-ok pedig ConfigMap-ként deployolhatóak a monitoring namespace-be.
