/** Teknik belgeler: her belge bir medya dosyasına sahiptir; yayın durumu dosyanın deposunu belirler. */
import type { DocumentType, MediaCategory } from '../lib/labels';
import { PRIVATE_BUCKET, PUBLIC_BUCKET } from '../lib/files';
import { AppError } from '../lib/errors';
import { invalidate } from '../lib/query';
import { documents, mediaRows, type Media, type TechDoc } from './entities';
import { deleteMedia, replaceMediaFile, setMediaBucket, uploadMedia } from './media';

export const docCategory: Record<DocumentType, MediaCategory> = {
  project_report: 'report', circuit_schematic: 'circuit_schematic', architecture_document: 'architecture_diagram',
  simulation_report: 'report', datasheet: 'technical_file', test_report: 'testing_evidence', meeting_notes: 'report',
  graduation_deliverable: 'report',
};

export interface DocInput {
  title: string;
  description: string | null;
  document_type: DocumentType;
  component_id: string | null;
  version: string;
  is_published: boolean;
}

export async function createDocument(file: File, input: DocInput, onProgress?: (p: number) => void): Promise<TechDoc> {
  const media = await uploadMedia(file, {
    bucket: input.is_published ? PUBLIC_BUCKET : PRIVATE_BUCKET,
    category: docCategory[input.document_type],
    title: input.title,
    component_id: input.component_id,
  }, onProgress);
  try {
    return await documents.insert({ ...input, file_id: media.id });
  } catch (e) {
    await deleteMedia(media).catch(() => undefined);
    throw e;
  }
}

/** Yayımlama: dosya önce herkese açık depoya taşınır. Yayından kaldırma: dosya özel depoya alınır. */
export async function setDocumentPublished(doc: TechDoc, media: Media, publish: boolean): Promise<void> {
  if (publish) {
    if (media.bucket_name !== PUBLIC_BUCKET) await setMediaBucket(media, PUBLIC_BUCKET);
    await documents.update(doc.id, { is_published: true }, doc.updated_at);
  } else {
    await documents.update(doc.id, { is_published: false }, doc.updated_at);
    const fresh = await mediaRows.get(media.id);
    try {
      await setMediaBucket(fresh, PRIVATE_BUCKET);
    } catch {
      throw new AppError('Belge yayından kaldırıldı ancak dosya özel depoya taşınamadı (ör. dosya türü özel depoda desteklenmiyor). Dosya bağlantısı hâlâ erişilebilir olabilir.', 'partial');
    }
  }
  invalidate('technical_documents', 'media_files');
}

export async function replaceDocumentFile(doc: TechDoc, media: Media, file: File, version: string, onProgress?: (p: number) => void) {
  await replaceMediaFile(media, file, onProgress);
  await documents.update(doc.id, { version }, doc.updated_at);
}

/** Belge silinince kendisine ait dosya da silinir. */
export async function deleteDocument(doc: TechDoc, media: Media | undefined) {
  await documents.remove(doc.id);
  if (media) await deleteMedia(media).catch(() => undefined);
  invalidate('media_files');
}
