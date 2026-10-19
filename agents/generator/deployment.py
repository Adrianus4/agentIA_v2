from __future__ import annotations

from contracts.models import FileContent
from contracts.solution_models import DeploymentSpec, MicroserviceSpec, ObservabilitySpec, SecuritySpec


class DeploymentGenerator:
    def generate(
        self,
        service: MicroserviceSpec,
        deployment: DeploymentSpec,
        observability: ObservabilitySpec,
        security: SecuritySpec,
    ) -> list[FileContent]:
        files: list[FileContent] = []
        app_name = service.service_name
        namespace = deployment.namespace

        if deployment.docker:
            files.append(
                FileContent(
                    path="Dockerfile",
                    content=(
                        f"FROM {deployment.base_image}\n"
                        "WORKDIR /work/\n"
                        "COPY target/quarkus-app/ /work/\n"
                        "EXPOSE 8080\n"
                        "USER 1001\n"
                        "ENV JAVA_OPTIONS=\"-Dquarkus.http.host=0.0.0.0\"\n"
                        "ENTRYPOINT [\"java\",\"-jar\",\"/work/quarkus-run.jar\"]\n"
                    ),
                )
            )
            # Allow target/quarkus-app/ in Docker build context while excluding other build intermediates
            files.append(
                FileContent(
                    path=".dockerignore",
                    content=".git\n__pycache__\n*.iml\ntarget/*\n!target/quarkus-app/\n",
                )
            )

        if deployment.kubernetes:
            files.append(
                FileContent(
                    path="k8s/deployment.yaml",
                    content=(
                        "apiVersion: apps/v1\n"
                        "kind: Deployment\n"
                        "metadata:\n"
                        f"  name: {app_name}\n"
                        f"  namespace: {namespace}\n"
                        "spec:\n"
                        f"  replicas: {deployment.replicas}\n"
                        "  selector:\n"
                        "    matchLabels:\n"
                        f"      app: {app_name}\n"
                        "  template:\n"
                        "    metadata:\n"
                        "      labels:\n"
                        f"        app: {app_name}\n"
                        "    spec:\n"
                        "      containers:\n"
                        "        - name: app\n"
                        f"          image: {app_name}:latest\n"
                        "          ports:\n"
                        "            - containerPort: 8080\n"
                        "          readinessProbe:\n"
                        "            httpGet:\n"
                        "              path: /q/health/ready\n"
                        "              port: 8080\n"
                        "          livenessProbe:\n"
                        "            httpGet:\n"
                        "              path: /q/health/live\n"
                        "              port: 8080\n"
                        "          envFrom:\n"
                        "            - configMapRef:\n"
                        f"                name: {app_name}-config\n"
                        "            - secretRef:\n"
                        f"                name: {app_name}-secret\n"
                        "          env:\n"
                        f"            - name: QUARKUS_LOG_CONSOLE_JSON\n              value: \"{'true' if observability.structured_logging else 'false'}\"\n"
                        f"            - name: SECURITY_MODE\n              value: \"{security.mode}\"\n"
                    ),
                )
            )
            files.append(
                FileContent(
                    path="k8s/service.yaml",
                    content=(
                        "apiVersion: v1\n"
                        "kind: Service\n"
                        "metadata:\n"
                        f"  name: {app_name}\n"
                        f"  namespace: {namespace}\n"
                        "spec:\n"
                        "  selector:\n"
                        f"    app: {app_name}\n"
                        "  ports:\n"
                        "    - port: 80\n"
                        "      targetPort: 8080\n"
                    ),
                )
            )
            files.append(
                FileContent(
                    path="k8s/configmap.yaml",
                    content=(
                        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n"
                        f"  name: {app_name}-config\n  namespace: {namespace}\n"
                        "data:\n"
                        f"  TRACE_ID_HEADER: \"{observability.trace_id_header}\"\n"
                    ),
                )
            )
            files.append(
                FileContent(
                    path="k8s/secret.example.yaml",
                    content=(
                        "apiVersion: v1\nkind: Secret\nmetadata:\n"
                        f"  name: {app_name}-secret\n  namespace: {namespace}\n"
                        "type: Opaque\nstringData:\n  oidc-client-secret: change-me\n"
                    ),
                )
            )

        if deployment.openshift:
            files.append(
                FileContent(
                    path="openshift/route.yaml",
                    content=(
                        "apiVersion: route.openshift.io/v1\n"
                        "kind: Route\n"
                        "metadata:\n"
                        f"  name: {app_name}\n"
                        "spec:\n"
                        "  to:\n"
                        "    kind: Service\n"
                        f"    name: {app_name}\n"
                    ),
                )
            )

        return files
