/**
 * Calendar Event Choices - Disambiguation UI.
 *
 * Shown when multiple events match user request.
 * Allows user to select which event they mean.
 */

import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Calendar, Video } from 'lucide-react';
import type { EventSummary } from '@/types/calendar';

interface Props {
  events: EventSummary[];
  message: string;
  onSelect?: (eventId: string) => void;
  onOpenCalendar?: () => void;
}

export function CalendarEventChoices({ events, message, onSelect, onOpenCalendar }: Props) {
  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle className="text-base">{message}</CardTitle>
      </CardHeader>

      <CardContent className="space-y-2">
        {/* Event choices */}
        {events.map((event) => {
          const startDate = new Date(event.starts_at);
          const duration = Math.round(
            (new Date(event.ends_at).getTime() - startDate.getTime()) / (1000 * 60)
          );

          return (
            <Button
              key={event.id}
              variant="outline"
              className="w-full h-auto py-3 justify-start"
              onClick={() => onSelect?.(event.id)}
              disabled={!onSelect}
            >
              <div className="flex items-start gap-3 w-full">
                <div
                  className={`p-1.5 rounded ${
                    event.provider === 'google' ? 'bg-blue-100 text-blue-600' : 'bg-purple-100 text-purple-600'
                  }`}
                >
                  <Calendar className="w-4 h-4" />
                </div>

                <div className="flex-1 text-left">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-medium">{event.title}</div>
                    <Badge variant="outline" className="shrink-0">
                      {event.provider === 'google' ? 'Google' : 'Outlook'}
                    </Badge>
                  </div>

                  <div className="text-sm text-muted-foreground mt-1">
                    {format(startDate, "EEE d MMM 'à' HH:mm", { locale: fr })} · {duration} min
                    {event.video_conference_link && (
                      <>
                        {' '}
                        · <Video className="w-3 h-3 inline" />
                      </>
                    )}
                  </div>
                </div>
              </div>
            </Button>
          );
        })}

        {/* Open calendar button */}
        {onOpenCalendar && (
          <>
            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">ou</span>
              </div>
            </div>

            <Button variant="secondary" className="w-full" onClick={onOpenCalendar}>
              <Calendar className="w-4 h-4 mr-2" />
              Ouvrir le calendrier
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
