/**
 * Calendar Event Card - Display event in chat.
 *
 * Shown after create/update/delete operations.
 */

import { Calendar, Video, ExternalLink, Clock, Users } from 'lucide-react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { EventSummary } from '@/types/calendar';

interface Props {
  event: EventSummary;
  message?: string;
}

export function CalendarEventCard({ event, message }: Props) {
  const startDate = new Date(event.starts_at);
  const endDate = new Date(event.ends_at);
  const duration = Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60));

  return (
    <Card className="max-w-2xl">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <div
            className={`p-2 rounded-lg ${
              event.provider === 'google' ? 'bg-blue-100 text-blue-600' : 'bg-purple-100 text-purple-600'
            }`}
          >
            <Calendar className="w-5 h-5" />
          </div>

          <div className="flex-1">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h4 className="font-medium text-base">{event.title}</h4>
                {message && <p className="text-sm text-muted-foreground mt-0.5">{message}</p>}
              </div>

              <Badge variant={event.provider === 'google' ? 'default' : 'secondary'}>
                {event.provider === 'google' ? 'Google' : 'Outlook'}
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Date & Time */}
        <div className="flex items-center gap-2 text-sm">
          <Clock className="w-4 h-4 text-muted-foreground" />
          <span>
            {format(startDate, "EEEE d MMMM 'à' HH:mm", { locale: fr })} ({duration} min)
          </span>
        </div>

        {/* Attendees */}
        {event.attendees && event.attendees.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <Users className="w-4 h-4 text-muted-foreground" />
            <span>
              {event.attendees.length} participant{event.attendees.length > 1 ? 's' : ''}
              {event.attendees.length <= 3 && ': ' + event.attendees.join(', ')}
            </span>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          {event.video_conference_link && (
            <Button size="sm" variant="default" asChild>
              <a href={event.video_conference_link} target="_blank" rel="noopener noreferrer">
                <Video className="w-4 h-4 mr-2" />
                Rejoindre la visio
              </a>
            </Button>
          )}

          {event.html_link && (
            <Button size="sm" variant="outline" asChild>
              <a href={event.html_link} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="w-4 h-4 mr-2" />
                Ouvrir dans {event.provider === 'google' ? 'Google' : 'Outlook'}
              </a>
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
