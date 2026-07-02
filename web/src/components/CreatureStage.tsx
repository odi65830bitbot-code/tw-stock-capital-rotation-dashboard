import type { CreatureProfile } from "../lib/creatureCardModel";

type CreatureStageProps = {
  profile: CreatureProfile;
};

export function CreatureStage({ profile }: CreatureStageProps) {
  const stageClass = `creature-stage ${profile.tone} ${profile.isFortuneAnimal ? "style-fortune-animal" : ""} status-${profile.profitStatus}`;
  
  return (
    <div className={stageClass}>
      <div className="creature-particles" />
      <div className="creature-light-beam" />
      <div className="creature-ground-shadow" />
      <div className="creature-body" aria-label={`${profile.archetypeLabel} ${profile.moodText}`}>
        <span className="creature-aura" />
        <span className="creature-shell" />
        <span className="creature-fin top" />
        <span className="creature-fin left" />
        <span className="creature-fin right" />
        <span className="creature-flame" />
        <span className="creature-crystal left" />
        <span className="creature-crystal right" />
        <span className="creature-ear left" />
        <span className="creature-ear right" />
        <span className="creature-wing left" />
        <span className="creature-wing right" />
        <span className="creature-tail" />
        <span className="creature-arm left" />
        <span className="creature-arm right" />
        <span className="creature-leg left" />
        <span className="creature-leg right" />
        <span className="creature-face">
          <span className="creature-eye left" />
          <span className="creature-eye right" />
          <span className="creature-mouth" />
        </span>
        <span className="creature-core" />
        
        {/* High-fidelity transparent 3D WebP/PNG creature image */}
        {profile.imagePath && (
          <img
            src={`${profile.imagePath}?v=20260614`}
            alt={profile.archetypeLabel}
            className="creature-avatar-img"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "contain",
              zIndex: 10,
              filter: profile.creatureFilter || "none",
            }}
          />
        )}
      </div>
      <div className="creature-nameplate">
        <strong>{profile.archetypeLabel}</strong>
        <span>{profile.moodText}</span>
      </div>
    </div>
  );
}
