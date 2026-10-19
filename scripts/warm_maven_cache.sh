#!/usr/bin/env bash
# ==============================================================================
# scripts/warm_maven_cache.sh
# Pre-warms the local ~/.m2 repository with Quarkus 3.15 dependencies
# Prevents initial verification timeouts on clean/fresh machines.
# ==============================================================================
set -euo pipefail

echo "======================================================================"
echo " AgentIA v2 - Pre-calentamiento de Caché Maven (~/.m2) Quarkus 3.15"
echo "======================================================================"

if ! command -v mvn &>/dev/null; then
    echo "ERROR: Maven ('mvn') no está instalado en el sistema."
    echo "Instálalo primero:"
    echo "  Fedora: sudo dnf install -y maven java-21-openjdk-devel"
    echo "  Ubuntu: sudo apt update && sudo apt install -y maven openjdk-21-jdk"
    exit 1
fi

M2_QUARKUS="$HOME/.m2/repository/io/quarkus/platform/quarkus-bom/3.15.1"
if [ -d "$M2_QUARKUS" ] && [ "${FORCE_WARMUP:-0}" != "1" ]; then
    echo "✓ Las dependencias principales de Quarkus 3.15.1 ya están presentes en ~/.m2."
    echo "  No es necesario pre-calentar (usa FORCE_WARMUP=1 para forzar)."
    exit 0
fi

WARMUP_DIR="/tmp/agentia-m2-warmup"
rm -rf "$WARMUP_DIR"
mkdir -p "$WARMUP_DIR"

echo "--> Creando proyecto mínimo de calentamiento Quarkus 3.15..."
cat << 'EOF' > "$WARMUP_DIR/pom.xml"
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.agentia.warmup</groupId>
    <artifactId>warmup-service</artifactId>
    <version>1.0.0</version>
    <properties>
        <compiler-plugin.version>3.13.0</compiler-plugin.version>
        <maven.compiler.release>21</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
        <quarkus.platform.group-id>io.quarkus.platform</quarkus.platform.group-id>
        <quarkus.platform.version>3.15.1</quarkus.platform.version>
        <surefire-plugin.version>3.3.1</surefire-plugin.version>
    </properties>
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>${quarkus.platform.group-id}</groupId>
                <artifactId>${quarkus.platform.artifact-id}</artifactId>
                <version>${quarkus.platform.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-arc</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-rest-jackson</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-hibernate-orm-panache</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-hibernate-validator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-jdbc-postgresql</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-jdbc-h2</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-smallrye-health</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-micrometer-registry-prometheus</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-smallrye-jwt</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-junit5</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>${quarkus.platform.group-id}</groupId>
                <artifactId>quarkus-maven-plugin</artifactId>
                <version>${quarkus.platform.version}</version>
                <extensions>true</extensions>
                <executions>
                    <execution>
                        <goals>
                            <goal>build</goal>
                            <goal>generate-code</goal>
                            <goal>generate-code-tests</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
            <plugin>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>${compiler-plugin.version}</version>
            </plugin>
            <plugin>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>${surefire-plugin.version}</version>
            </plugin>
        </plugins>
    </build>
</project>
EOF

mkdir -p "$WARMUP_DIR/src/main/java/com/agentia/warmup"
cat << 'EOF' > "$WARMUP_DIR/src/main/java/com/agentia/warmup/WarmupApp.java"
package com.agentia.warmup;
import jakarta.enterprise.context.ApplicationScoped;
@ApplicationScoped
public class WarmupApp {}
EOF

echo "--> Descargando BOM, plugins y dependencias en ~/.m2 (puede tardar 2-3 minutos en la primera ejecución)..."
(cd "$WARMUP_DIR" && mvn -B test-compile)

echo "--> Limpiando directorio temporal de calentamiento..."
rm -rf "$WARMUP_DIR"

echo "======================================================================"
echo " ✓ Caché Maven pre-calentada con éxito."
echo "   Todas las ejecuciones y verificaciones de AgentIA ahora compilarán en segundos."
echo "======================================================================"
