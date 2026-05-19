import { Link } from "react-router-dom";

export default function Landing() {
  return (
    <div
      style={{
        minHeight: "100vh",
        fontFamily: "'DM Sans', sans-serif",
        background:
          "radial-gradient(circle at top, #f6f1ea, #efe7dc 40%, #e9dfd2 100%)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* soft background blobs */}
      <div
        style={{
          position: "absolute",
          width: "400px",
          height: "400px",
          background: "rgba(180, 140, 120, 0.25)",
          borderRadius: "50%",
          filter: "blur(120px)",
          top: "-100px",
          left: "-100px",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: "350px",
          height: "350px",
          background: "rgba(120, 150, 120, 0.2)",
          borderRadius: "50%",
          filter: "blur(120px)",
          bottom: "-120px",
          right: "-80px",
        }}
      />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          minHeight: "100vh",
          padding: "2rem",
          maxWidth: 900,
          margin: "0 auto",
          position: "relative",
          zIndex: 2,
        }}
      >
        {/* Brand */}
        <div
          style={{
            fontFamily: "'Fraunces', serif",
            fontSize: "3.5rem",
            fontWeight: 300,
            letterSpacing: "-1px",
            color: "var(--moss)",
          }}
        >
          SALIT
          <em style={{ fontStyle: "italic", color: "var(--clay)" }}>A</em>
          yo
        </div>

        {/* Tagline */}
        <p
          style={{
            marginTop: "1rem",
            color: "rgba(60,60,60,0.75)",
            fontSize: "1.1rem",
            fontWeight: 300,
            maxWidth: 520,
            lineHeight: 1.8,
          }}
        >
          A dyslexia-friendly reading companion designed to help every learner
          build confidence, one word at a time.
        </p>

        {/* CTA buttons */}
        <div
          style={{
            display: "flex",
            gap: "1rem",
            marginTop: "2rem",
            flexWrap: "wrap",
          }}
        >
          <Link
            to="/signup"
            style={{
              padding: "12px 28px",
              borderRadius: "999px",
              background:
                "linear-gradient(135deg, var(--clay), #c57b5f)",
              color: "white",
              textDecoration: "none",
              fontSize: "0.95rem",
              boxShadow: "0 10px 30px rgba(0,0,0,0.12)",
              transition: "transform 0.2s ease, box-shadow 0.2s ease",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.boxShadow =
                "0 14px 40px rgba(0,0,0,0.18)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow =
                "0 10px 30px rgba(0,0,0,0.12)";
            }}
          >
            Get started
          </Link>

          <Link
            to="/login"
            style={{
              padding: "12px 28px",
              borderRadius: "999px",
              border: "1px solid rgba(60, 80, 60, 0.3)",
              color: "var(--moss)",
              textDecoration: "none",
              fontSize: "0.95rem",
              backdropFilter: "blur(10px)",
              background: "rgba(255,255,255,0.35)",
              transition: "transform 0.2s ease, background 0.2s ease",
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.transform = "translateY(-2px)";
              e.currentTarget.style.background =
                "rgba(255,255,255,0.55)";
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.background =
                "rgba(255,255,255,0.35)";
            }}
          >
            Log in
          </Link>
        </div>
      </div>
    </div>
  );
}