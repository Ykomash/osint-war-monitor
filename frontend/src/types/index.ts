export interface NewsArticle {
  id: number;
  source: string;
  title: string;
  url: string;
  description: string;
  published_at: string | null;
  category: string;
  image_url: string | null;
}

export interface TelegramMessage {
  id: number;
  channel_id: number;
  channel_name: string;
  message_id: number;
  text: string;
  timestamp: string;
  has_media: boolean;
  media_type: string | null;
  media_file: string | null;
  is_flagged: boolean;
  matched_keywords: string[];
}

export interface TelegramChannel {
  id: number;
  channel_identifier: string;
  display_name: string;
  is_active: boolean;
  added_at: string;
}

export interface AISummary {
  id?: number;
  content: string | null;
  generated_at: string | null;
  period_hours?: number;
}

export interface WSMessage {
  type: string;
  data: Record<string, unknown>;
}
