import { test, expect } from '@playwright/test';
import JSZip from 'jszip';
import fs from 'node:fs';

test.describe('Studio Functional Walkthrough & Validation (U05–U06)', () => {
  test.beforeEach(async ({ page }) => {
    // Garantizar un contexto y almacenamiento limpios en cada caso (AC-14, AC-17)
    // e inyectar la URL del backend del harness y clave de API si están definidas
    const backendUrl = process.env.BACKEND_URL;
    const apiKey = process.env.ORCHESTRATOR_API_KEY || process.env.AGENTIA_API_KEY;
    await page.addInitScript(({ url, key }) => {
      window.localStorage.clear();
      window.sessionStorage.clear();
      if (url) {
        window.localStorage.setItem('agentia_v2_backend_url', url);
      }
      if (key) {
        window.localStorage.setItem('agentia_v2_api_key', key);
      }
    }, { url: backendUrl, key: apiKey });
  });

  test('U05 / AC-14 / AC-15: Flujo completo desde sesión limpia, aprobación en LangGraph y descarga de ZIP real verificado', async ({ page, request }) => {
    test.setTimeout(240_000);

    const backendUrl = process.env.BACKEND_URL || 'http://127.0.0.1:8000';
    const apiKey = process.env.ORCHESTRATOR_API_KEY || 'secret';

    // 1. Cargar la aplicación
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /AgentIA/i })).toBeVisible({ timeout: 15_000 });

    // 2. Rechazar sesiones de demostración precargadas e iniciar una sesión nueva limpia (AC-14)
    const newServiceBtn = page.getByRole('button', { name: /\+ Nuevo Microservicio/i });
    await expect(newServiceBtn).toBeVisible();
    await newServiceBtn.click();

    // 3. Verificar que estamos en la etapa 1 limpia (Especificación)
    await expect(page.getByText('1. Especificación del Microservicio')).toBeVisible({ timeout: 10_000 });

    // Seleccionar plantilla de especificación para la nueva sesión limpia
    const presetBtn = page.getByRole('button', { name: /Order Management \(Hexagonal \+ Reactive\)/i }).first();
    await expect(presetBtn).toBeVisible();
    await presetBtn.click();

    // Continuar a la etapa 2: Arquitectura & Modelos
    const continueBtn = page.getByRole('button', { name: /Continuar a Arquitectura & Modelos/i }).first();
    await expect(continueBtn).toBeVisible();
    await continueBtn.click();

    // 4. Verificar llegada a la etapa 2 (Arquitectura & Modelos)
    await expect(page.getByRole('heading', { name: /Arquitectura Hexagonal & Modelos de Dominio/i })).toBeVisible({ timeout: 15_000 });

    // 5. Disparar generación real: Aprobar y Generar Microservicio
    const approveBtn = page.getByRole('button', { name: /Aprobar y Generar Microservicio/i }).first();
    await expect(approveBtn).toBeVisible();

    // Esperar la petición HTTP al orquestador
    const runResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/v1/blueprint/run') || resp.url().includes('/v1/runs'),
      { timeout: 30_000 }
    );
    await approveBtn.click();
    const runResponse = await runResponsePromise;
    expect(runResponse.status()).toBeLessThan(400);

    // R03: Capturar solicitud y verificar estado terminal SUCCESS y verification.success por API
    const runData = await runResponse.json();
    const traceId = runData.trace_id || runData.state?.trace_id;
    expect(traceId).toBeTruthy();

    // Esperar a que la ejecución concluya en la interfaz (botón rehabilitado)
    await expect(approveBtn).toBeEnabled({ timeout: 180_000 });
    await expect(page.locator('text=Ejecutando en LangGraph...').first()).not.toBeVisible({ timeout: 10_000 });

    // R03: Consultar endpoint de estado /v1/blueprint/status/{trace_id} con request fixture
    const statusRes = await request.get(`${backendUrl}/v1/blueprint/status/${traceId}`, {
      headers: { 'x-api-key': apiKey },
    });
    expect(statusRes.status()).toBe(200);
    const statusData = await statusRes.json();
    expect(statusData.status).toBe('SUCCESS');
    const stateObj = statusData.state || statusData;
    expect(stateObj.verification?.success).toBe(true);

    // Cerrar el drawer de telemetría si está abierto para liberar la vista e interacción
    const closeDrawerBtn = page.locator('button[title="Ocultar terminal de telemetría"]');
    if (await closeDrawerBtn.isVisible()) {
      await closeDrawerBtn.click();
      await page.waitForTimeout(300);
    }

    // 6. Navegar a la etapa 5: DevOps, Despliegue & Entrega Git
    const devopsTab = page.getByRole('button', { name: /5\. DevOps & Despliegue/i }).first();
    await expect(devopsTab).toBeVisible();
    await devopsTab.click();

    await expect(page.getByText('Etapa 5: DevOps, Despliegue & Entrega Git')).toBeVisible({ timeout: 10_000 });

    // 7. Cambiar al sub-tab: Entrega Git & ZIP (Código Real)
    const gitSubTab = page.getByRole('button', { name: /Entrega Git & ZIP \(Código Real\)/i }).first();
    await expect(gitSubTab).toBeVisible();
    await gitSubTab.click();

    // 8. Descargar ZIP y validar contenido real (AC-15: sin fallback a solo README)
    const downloadBtn = page.getByRole('button', { name: /Descargar Código \(\.ZIP\)/i }).first();
    await expect(downloadBtn).toBeVisible();

    const downloadPromise = page.waitForEvent('download', { timeout: 15_000 });
    await downloadBtn.click();
    const download = await downloadPromise;

    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    if (!downloadPath) throw new Error('No se descargó el archivo ZIP');

    const zipBuffer = fs.readFileSync(downloadPath);
    const zip = await JSZip.loadAsync(zipBuffer);
    const files = Object.keys(zip.files).filter((name) => !zip.files[name].dir);

    // AC-15: Debe contener pom.xml, fuentes Java y no ser solo README ni vacío
    expect(files.length).toBeGreaterThan(1);
    expect(files).toContain('pom.xml');
    const javaFiles = files.filter((f) => f.endsWith('.java'));
    expect(javaFiles.length).toBeGreaterThan(0);

    // R03: Verificar presencia de pruebas JUnit/QuarkusTest generadas
    const testFiles = files.filter((f) => f.includes('Test.java') || f.includes('IT.java'));
    expect(testFiles.length).toBeGreaterThan(0);

    const isOnlyReadme = files.length === 1 && files[0].toLowerCase().includes('readme');
    expect(isOnlyReadme).toBe(false);

    // R03 / S12: Contrastar obligatoriamente la presencia y contenido exacto de los archivos generados dentro del ZIP
    const genFiles = stateObj.generated_files;
    expect(Array.isArray(genFiles) && genFiles.length > 0).toBe(true);
    for (const gf of genFiles) {
      if (gf.path) {
        const normPath = gf.path.replace(/^[/\\]+/, '');
        const entry = zip.file(normPath);
        expect(entry).not.toBeNull();
        if (gf.content && entry) {
          const actualText = await entry.async('string');
          expect(actualText.trim()).toBe(gf.content.trim());
        }
      }
    }
  });

  test('U06 / AC-16: Muestra rechazo visible ante autenticación inválida (401) contra backend real', async ({ page }) => {
    // R04: Usar clave incorrecta contra el backend real sin route.fulfill
    const backendUrl = process.env.BACKEND_URL;
    await page.addInitScript(({ url }) => {
      window.localStorage.clear();
      window.sessionStorage.clear();
      if (url) {
        window.localStorage.setItem('agentia_v2_backend_url', url);
      }
      window.localStorage.setItem('agentia_v2_api_key', 'invalid-secret-key-that-fails-auth');
    }, { url: backendUrl });

    await page.goto('/');

    // Abrir ventana emergente de Configuración
    const settingsBtn = page.getByTitle('Abrir ventana emergente de Configuración del Motor LLM');
    await expect(settingsBtn).toBeVisible({ timeout: 15_000 });
    await settingsBtn.click();

    // Disparar verificación de conexión contra backend con credencial inválida
    const testConnBtn = page.getByRole('button', { name: /Probar Conexión/i });
    await expect(testConnBtn).toBeVisible();
    await testConnBtn.click();

    // R04: Asertar explícitamente y sin condicionales que se muestra el error 401 devuelto por el backend
    await expect(
      page.getByText('Error de autenticación (401)').first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test('U06 / AC-16: Detecta fallo de caída backend sin mostrar éxito falso', async ({ page }) => {
    // R04: Apuntar a un puerto loopback no disponible para validar detección de caída real
    await page.addInitScript(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
      window.localStorage.setItem('agentia_v2_backend_url', 'http://127.0.0.1:59999');
      window.localStorage.setItem('agentia_v2_api_key', 'dummy-key');
    });

    await page.goto('/');

    // R04: Verificar que el indicador en el header detecta estado DOWN sin simulación
    await expect(
      page.locator('[title*="FastAPI Orchestrator: DOWN"]').or(page.locator('text=DOWN'))
    ).toBeVisible({ timeout: 20_000 });
  });
});
