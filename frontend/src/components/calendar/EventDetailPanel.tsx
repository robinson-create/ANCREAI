/**
 * Event detail panel - Shows event details in sidebar.
 *
 * Features:
 * - Display all event information
 * - Join video link button
 * - Open in Google/Outlook link
 * - Edit/Delete actions (TODO: implement)
 */

import { useMemo } from 'react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { X, Video, ExternalLink, Calendar, Clock, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { EventSummary } from '@/types/calendar';

interface Props {
  eventId: string;
  events: EventSummary[];
  onClose: () => void;
}

export function EventDetailPanel({ eventId, events, onClose }: Props) {
  const event = useMemo(() => {
    return events.find((e) => e.id === eventId);
  }, [eventId, events]);

  if (!event) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <p className="text-muted-foreground">Événement introuvable</p>
        <Button variant="ghost" size="sm" onClick={onClose} className="mt-4">
          Fermer
        </Button>
      </div>
    );
  }

  const startDate = new Date(event.starts_at);
  const endDate = new Date(event.ends_at);
  const duration = Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b">
        <div className="flex-1 pr-4">
          <h3 className="text-lg font-semibold line-clamp-2">{event.title}</h3>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant={event.provider === 'google' ? 'default' : 'secondary'}>
              {event.provider === 'google' ? 'Google' : 'Outlook'}
            </Badge>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Date & Time */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <Calendar className="w-4 h-4 text-muted-foreground" />
            <span className="font-medium">
              {format(startDate, "EEEE d MMMM yyyy", { locale: fr })}
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Clock className="w-4 h-4 text-muted-foreground" />
            <span>
              {format(startDate, 'HH:mm')} - {format(endDate, 'HH:mm')} ({duration} min)
            </span>
          </div>
        </div>

        <Separator />

        {/* Attendees */}
        {event.attendees && event.attendees.length > 0 && (
          <>
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Users className="w-4 h-4 text-muted-foreground" />
                <span>Participants ({event.attendees.length})</span>
              </div>
              <ul className="space-y-1 pl-6">
                {event.attendees.slice(0, 5).map((email, idx) => (
                  <li key={idx} className="text-sm text-muted-foreground">
                    {email}
                  </li>
                ))}
                {event.attendees.length > 5 && (
                  <li className="text-sm text-muted-foreground">
                    +{event.attendees.length - 5} autres
                  </li>
                )}
              </ul>
            </div>
            <Separator />
          </>
        )}

        {/* Description */}
        {event.description && (
          <>
            <div className="space-y-2">
              <div className="text-sm font-medium">Description</div>
              <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                {event.description}
              </p>
            </div>
            <Separator />
          </>
        )}

        {/* Video Conference */}
        {event.video_conference_link && (
          <>
            <div className="space-y-2">
              <Button asChild className="w-full">
                <a href={event.video_conference_link} target="_blank" rel="noopener noreferrer">
                  <Video className="w-4 h-4 mr-2" />
                  Rejoindre la visio
                </a>
              </Button>
            </div>
            <Separator />
          </>
        )}

        {/* Calendar Link */}
        {event.html_link && (
          <Button variant="outline" asChild className="w-full">
            <a href={event.html_link} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="w-4 h-4 mr-2" />
              Ouvrir dans {event.provider === 'google' ? 'Google Calendar' : 'Outlook'}
            </a>
          </Button>
        )}

        {/* TODO: Edit/Delete actions */}
        {/* <div className="flex gap-2 pt-4">
          <Button variant="outline" className="flex-1">
            Modifier
          </Button>
          <Button variant="destructive" className="flex-1">
            Supprimer
          </Button>
        </div> */}
      </div>
    </div>
  );
}
