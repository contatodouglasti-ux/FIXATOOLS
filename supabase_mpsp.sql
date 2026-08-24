-- Estrutura das tabelas usadas pelo Coletor BI para o MPSP.
-- Execute este script no SQL Editor do projeto Supabase antes da coleta.

CREATE TABLE IF NOT EXISTS public.bi_peticionamento_hora_mpsp (
    hora_inicio timestamp without time zone NOT NULL,
    hora_fim timestamp without time zone NOT NULL,
    protocolado_saj6 bigint NOT NULL DEFAULT 0,
    protocolado_saj5 bigint NOT NULL DEFAULT 0,
    falha_saj6 bigint NOT NULL DEFAULT 0,
    falha_saj5 bigint NOT NULL DEFAULT 0,
    CONSTRAINT bi_peticionamento_hora_mpsp_pkey PRIMARY KEY (hora_inicio)
);

CREATE TABLE IF NOT EXISTS public.bi_intimacao_hora_mpsp (
    hora_inicio timestamp without time zone NOT NULL,
    hora_fim timestamp without time zone NOT NULL,
    intimacao bigint NOT NULL DEFAULT 0,
    CONSTRAINT bi_intimacao_hora_mpsp_pkey PRIMARY KEY (hora_inicio)
);

CREATE TABLE IF NOT EXISTS public.bi_peticionamento_mensal_motivo_mpsp (
    dia_referencia date NOT NULL,
    flstatus text NOT NULL,
    demotivofalha text NOT NULL,
    total bigint NOT NULL DEFAULT 0,
    CONSTRAINT bi_peticionamento_mensal_motivo_mpsp_pkey
        PRIMARY KEY (dia_referencia, flstatus, demotivofalha)
);

-- O Coletor BI usa a chave anon do Supabase para fazer upsert.
-- Se o projeto usar políticas RLS próprias, mantenha as políticas já
-- existentes e ajuste apenas as permissões necessárias para estas tabelas.
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE
    public.bi_peticionamento_hora_mpsp,
    public.bi_intimacao_hora_mpsp,
    public.bi_peticionamento_mensal_motivo_mpsp
TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
