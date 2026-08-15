import runeDividerSvg from '../assets/skyrim-ui/rune-divider.svg';

export function RuneDivider() {
  return (
    <div className="rune-divider-wrapper" aria-hidden="true" role="presentation">
      <img
        src={runeDividerSvg}
        alt=""
        className="rune-divider-svg"
      />
    </div>
  );
}

export default RuneDivider;
