import { createPortal } from "react-dom";
import { useEffect } from "react";
import type { CardTemplateEntry } from "../types";

interface CardDrawModalProps {
  card: CardTemplateEntry;
  tileName?: string | null;
  onClose: () => void;
}

export function CardDrawModal({ card, tileName, onClose }: CardDrawModalProps) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const overlay = (
    <div
      className="card-draw-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="card-draw-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="card-draw-modal" onClick={(e) => e.stopPropagation()}>
        {tileName && <div className="card-draw-modal-caption">Landed on {tileName} - card drawn</div>}
        <div className="card-draw-modal-content">
          <h3 className="card-draw-modal-title" id="card-draw-modal-title">
            {card.title || "Untitled"}
          </h3>
          {card.image_url && (
            <div className="card-draw-modal-image-wrap">
              <img
                src={card.image_url}
                alt=""
                className="card-draw-modal-image"
                loading="lazy"
              />
            </div>
          )}
          {card.body && (
            <div className="card-draw-modal-body">{card.body}</div>
          )}
        </div>
        <button
          type="button"
          className="card-draw-modal-close primary"
          onClick={onClose}
          autoFocus
        >
          Close
        </button>
      </div>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(overlay, document.body)
    : null;
}
