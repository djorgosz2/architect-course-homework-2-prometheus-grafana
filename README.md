# Monitoring & Alerting rendszer - Hazi feladat

## Architektura

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

## Gyors inditas

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

A load generator automatikusan indul es forgalmat general, igy a dashboardon par perc utan lathatoak lesznek a metrikak.

## Metrikagyujtes

### Alkalmazas metrikak (OpenTelemetry + Prometheus exporter, port 9464)
- `http_server_request_duration_seconds` - HTTP RED metrikak (auto-instrumentation)
- `myapp_operations_total` - Uzleti muveletek szamlalo (success/error)
- `myapp_request_processing_duration_seconds` - Feldolgozasi ido
- `myapp_external_api_duration_seconds` - Kulso API hivasok ideje
- `myapp_db_connections_active` - Aktiv DB kapcsolatok szama

### Infrastruktura metrikak
- **cAdvisor** (port 8080): `container_memory_usage_bytes`, `container_cpu_usage_seconds_total`, `container_spec_memory_limit_bytes`
- **Node Exporter** (port 9100): `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `node_filesystem_avail_bytes`

## Dashboard panelek (Application Overview)

| #  | Panel                              | Metrika tipus        | Cel                                           |
|----|------------------------------------|----------------------|-----------------------------------------------|
| 1  | HTTP Request Rate by Status Code   | RED - Rate           | Forgalom osszkepe statusz kodonkent           |
| 2  | HTTP Error Rate                    | RED - Errors         | 4xx+5xx arany, 5%-os alert kuszob jelzesevel  |
| 3  | HTTP Request Duration (Latency)    | RED - Duration       | p50, p95, p99 percentilisek + atlag           |
| 4  | Business Operations by Status      | App-specifikus       | Uzleti muveletek success/error bontasban      |
| 5  | Container Memory Usage / Limit     | Infrastruktura       | Memoria hasznalatot a limithez merik (80% alert) |
| 6  | Container CPU Usage                | Infrastruktura       | CPU hasznalat kontenerenkent                  |
| 7  | Disk Usage                         | Infrastruktura       | Host szintu lemezhasznalat                    |

Kiegeszito stat panelek: Application Status (up/down), Current Request Rate, Current Error Rate, P95 Latency,
Node Memory Usage, Node CPU Usage.

## Alerting szabalyok

| Alert                    | Feltetel                                      | Severity | For   |
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

Az alertek az Alertmanager UI-ban lathatoak (http://localhost:9093), es a Grafana-ban is megjelennek.
Eles kornyezetben a `alertmanager.yml`-ben konfiguralhato Slack / Email / PagerDuty ertesites.

## Leallitas

```bash
docker compose down          # kontenerek leallitasa (adatok megmaradnak)
docker compose down -v       # kontenerek + volume-ok torlese
```

## Kapcsolodas Kubernetes-hez

Ez a Docker Compose setup a kovetkezo K8s komponenseket szimulaja:
- **cAdvisor** → kubelet beepitett container metrics
- **Node Exporter** → node-exporter DaemonSet
- **Prometheus scrape annotations** → `prometheus.io/scrape: "true"` pod annotaciok
- **Alertmanager** → kube-prometheus-stack AlertManager
- **Grafana provisioning** → ConfigMap-alapu dashboard deploy (`grafana_dashboard: "1"` label)

Eles K8s kornyezetben a metrikak automatikusan elerhetek a kube-prometheus-stack-en keresztul,
a dashboard JSON-ok pedig ConfigMap-kent deployolhatoak a monitoring namespace-be.
