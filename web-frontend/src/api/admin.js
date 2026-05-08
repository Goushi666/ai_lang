import request from "@/utils/request";

export const adminApi = {
  /** 清空 sensor_data / environment_anomalies（同一 SQLite 内两张表） */
  purgeData: (data) => request.post("/api/admin/purge-data", data),

  /** 列出 backend/knowledge_docs 下的 .md（仅管理员） */
  listKnowledgeDocs: () => request.get("/api/admin/knowledge/docs"),

  /** 上传 UTF-8 .md 到 knowledge_docs */
  uploadKnowledgeDoc: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return request.post("/api/admin/knowledge/docs/upload", fd, {
      timeout: 120000,
    });
  },

  /** 将目录下全部 .md 写入 FTS 知识索引 */
  ragImportAllFromDocs: () =>
    request.post("/api/admin/knowledge/rag/import-all", {}, { timeout: 120000 }),

  /** 单个文件导入索引 */
  ragImportOneFromDocs: (filename) =>
    request.post("/api/admin/knowledge/rag/import-one", { filename }, { timeout: 120000 }),

  /** 清空 FTS 知识索引（不可恢复） */
  ragClearAll: () => request.delete("/api/admin/knowledge/rag/clear"),

  /** 按 source 删除某文档在索引中的全部块 */
  ragDeleteBySource: (sourceId) =>
    request.delete(`/api/admin/knowledge/rag/source/${encodeURIComponent(sourceId)}`),

  /** 仅删除磁盘上的 knowledge_docs 文件（不自动删索引） */
  deleteKnowledgeDocFile: (filename) =>
    request.delete(`/api/admin/knowledge/docs/${encodeURIComponent(filename)}`),
};
