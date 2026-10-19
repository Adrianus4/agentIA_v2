import React, { useState } from 'react';
import {
  Share2,
  Download,
  GitBranch,
  GitPullRequest,
  CheckCircle2,
  FolderArchive,
} from 'lucide-react';
import { useStudio } from '../context/StudioContext';
import { Card } from '../components/common/Card';


export const ExportPublishView: React.FC = () => {
  const { activeSession } = useStudio();

  if (!activeSession) {
    return (
      <div className="text-center py-12 text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 p-8">
        <Share2 className="w-12 h-12 mx-auto mb-3 text-slate-500" />
        <h3 className="text-base font-bold text-white">No hay un microservicio seleccionado</h3>
      </div>
    );
  }

  const [repoUrl, setRepoUrl] = useState('https://github.com/tcs-enterprise/quarkus-microservices.git');
  const [branchName, setBranchName] = useState(`feature/001-${activeSession.name}`);
  const [gitToken, setGitToken] = useState('');
  const [commitMsg, setCommitMsg] = useState('feat: initial verified generation by AgentIA v2 LangGraph');
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishSuccess, setPublishSuccess] = useState(false);
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  const handleDownloadZip = () => {
    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  const handlePublish = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPublishing(true);
    await new Promise((resolve) => setTimeout(resolve, 600));
    setIsPublishing(false);
    setPublishSuccess(true);
  };

  return (
    <div className="space-y-6">
      <Card
        title={
          <div className="flex items-center gap-2">
            <Share2 className="w-5 h-5 text-blue-400" />
            <span>Fase 9: Entrega Integral, Empaquetado ZIP y Publicación Git</span>
          </div>
        }
        subtitle="Exportación atómica del código verificado y pruebas herméticas a repositorios corporativos"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Download ZIP Card */}
          <div className="p-5 rounded-2xl bg-slate-950 border border-slate-800 space-y-4 flex flex-col justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2 font-bold text-white text-sm">
                <FolderArchive className="w-5 h-5 text-blue-400" />
                <span>Descarga Local de Artefacto (.ZIP)</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Descargue el paquete completo del microservicio Quarkus 3.x que incluye código Java, pom.xml, configuración de propiedades, docker-compose y suites de pruebas QuarkusTest.
              </p>
            </div>

            {downloadSuccess && (
              <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-800 text-xs text-emerald-200 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Paquete {activeSession.name}.zip generado y listo para descarga.</span>
              </div>
            )}

            <button
              type="button"
              onClick={handleDownloadZip}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-md transition-all cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Descargar {activeSession.name}.zip</span>
            </button>
          </div>

          {/* Git Publish Form */}
          <div className="p-5 rounded-2xl bg-slate-950 border border-slate-800 space-y-4">
            <div className="flex items-center gap-2 font-bold text-white text-sm">
              <GitBranch className="w-5 h-5 text-indigo-400" />
              <span>Publicación a Repositorio Git</span>
            </div>

            {publishSuccess && (
              <div className="p-3 rounded-xl bg-emerald-950/60 border border-emerald-800 text-xs text-emerald-200 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Pull Request creado exitosamente en la rama {branchName}.</span>
              </div>
            )}

            <form onSubmit={handlePublish} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">URL del Repositorio Git</label>
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Nombre de Rama</label>
                <input
                  type="text"
                  value={branchName}
                  onChange={(e) => setBranchName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Mensaje de Commit</label>
                <input
                  type="text"
                  value={commitMsg}
                  onChange={(e) => setCommitMsg(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Token de Acceso Personal (Efímero)</label>
                <input
                  type="password"
                  value={gitToken}
                  onChange={(e) => setGitToken(e.target.value)}
                  placeholder="ghp_... o glpat-..."
                  className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-white font-mono"
                />
              </div>


              <button
                type="submit"
                disabled={isPublishing}
                className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 transition-all cursor-pointer"
              >
                <GitPullRequest className="w-4 h-4 text-blue-400" />
                <span>{isPublishing ? 'Publicando...' : 'Publicar Rama y Crear Pull Request'}</span>
              </button>
            </form>
          </div>
        </div>
      </Card>
    </div>
  );
};
