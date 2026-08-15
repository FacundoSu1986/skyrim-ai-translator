import dragonMedallionImg from '../assets/skyrim-ui/dragon-medallion.jpg';

export function DragonMedallion() {
  return (
    <div className="dragon-medallion-wrapper">
      <div className="dragon-medallion-frame">
        <img
          src={dragonMedallionImg}
          alt="Emblema del Dragón de Skyrim Translator"
          className="dragon-medallion-image"
        />
        <div className="medallion-overlay-rim" aria-hidden="true" />
      </div>
    </div>
  );
}

export default DragonMedallion;
