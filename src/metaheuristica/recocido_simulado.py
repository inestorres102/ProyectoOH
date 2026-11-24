
import math
import random
import time

from .evaluacion import (
    comprobar_restricciones,
    calcular_coste,
)

from .movimientos import generar_vecino


# ---------------------------------------------------------
# CONFIGURACIÓN DEL ALGORITMO
# ---------------------------------------------------------

TEMPERATURA_INICIAL = 10.0
TEMPERATURA_FINAL = 0.01
FACTOR_ENFRIAMIENTO = 0.995

ITERACIONES_MAXIMAS = 1000


# ---------------------------------------------------------
# ACEPTACIÓN DE SOLUCIONES
# ---------------------------------------------------------

def aceptar_solucion(
    coste_actual,
    coste_nuevo,
    temperatura,
    generador=None
):
    """Decide si se acepta una nueva solución."""

    diferencia = coste_nuevo - coste_actual

    if diferencia <= 0:
        return True

    if temperatura <= 0:
        return False

    probabilidad = math.exp(
        -diferencia / temperatura
    )

    if generador is None:
        generador = random.Random()

    return generador.random() < probabilidad


# ---------------------------------------------------------
# ALGORITMO PRINCIPAL
# ---------------------------------------------------------

def ejecutar_recocido_simulado(
    df_inicial,
    horas_por_dia=6,
    temperatura_inicial=TEMPERATURA_INICIAL,
    temperatura_final=TEMPERATURA_FINAL,
    factor_enfriamiento=FACTOR_ENFRIAMIENTO,
    iteraciones_maximas=ITERACIONES_MAXIMAS,
    semilla=None,
    mostrar_progreso=True,
    df_aulas=None
):
    """
    Ejecuta el algoritmo de recocido simulado.

    Parámetros:
        df_inicial:
            DataFrame con el horario inicial.

        horas_por_dia:
            Número de slots disponibles por día.

        df_aulas:
            Catálogo de aulas. Si se proporciona, se activa
            el movimiento de cambio de aula.

        temperatura_inicial:
            Temperatura inicial del algoritmo.

        temperatura_final:
            Temperatura a la que termina el enfriamiento.

        factor_enfriamiento:
            Factor multiplicativo de reducción de temperatura.

        iteraciones_maximas:
            Número máximo de iteraciones.

        semilla:
            Semilla aleatoria para reproducir experimentos.

        mostrar_progreso:
            Indica si se muestran mensajes durante la ejecución.

    Devuelve:
        Diccionario con el mejor horario y estadísticas.
    """

    tiempo_inicio = time.perf_counter()

    # -----------------------------------------------------
    # VALIDACIÓN DE PARÁMETROS
    # -----------------------------------------------------

    if df_inicial is None or df_inicial.empty:
        raise ValueError(
            "No se puede optimizar un horario vacío."
        )

    if horas_por_dia not in (6, 8):
        raise ValueError(
            "Las horas por día deben ser 6 u 8."
        )

    if temperatura_inicial <= 0:
        raise ValueError(
            "La temperatura inicial debe ser positiva."
        )

    if temperatura_final <= 0:
        raise ValueError(
            "La temperatura final debe ser positiva."
        )

    if temperatura_final >= temperatura_inicial:
        raise ValueError(
            "La temperatura final debe ser menor que la inicial."
        )

    if not 0 < factor_enfriamiento < 1:
        raise ValueError(
            "El factor de enfriamiento debe estar entre 0 y 1."
        )

    if iteraciones_maximas <= 0:
        raise ValueError(
            "El número máximo de iteraciones debe ser positivo."
        )

    if df_aulas is not None and df_aulas.empty:
        raise ValueError(
            "El catálogo de aulas está vacío."
        )

    generador = random.Random(semilla)

    # -----------------------------------------------------
    # COMPROBAR SOLUCIÓN INICIAL
    # -----------------------------------------------------

    valido, errores = comprobar_restricciones(
        df_inicial,
        horas_por_dia
    )

    if not valido:
        raise ValueError(
            "El horario inicial incumple restricciones:\n"
            + "\n".join(errores[:10])
        )

    # -----------------------------------------------------
    # INICIALIZACIÓN
    # -----------------------------------------------------

    solucion_actual = df_inicial.copy(deep=True)

    mejor_solucion = df_inicial.copy(deep=True)

    coste_actual = calcular_coste(
        solucion_actual,
        horas_por_dia
    )

    mejor_coste = coste_actual

    coste_inicial = coste_actual

    temperatura = temperatura_inicial

    iteraciones = 0
    aceptados = 0
    mejoras = 0
    soluciones_peores_aceptadas = 0
    movimientos_fallidos = 0

    historial = []

    if mostrar_progreso:

        print("\n" + "=" * 60)
        print("INICIANDO RECOCIDO SIMULADO")
        print("=" * 60)

        print(f"Coste inicial: {coste_inicial}")
        print(f"Temperatura inicial: {temperatura_inicial}")
        print(f"Temperatura final: {temperatura_final}")
        print(f"Factor de enfriamiento: {factor_enfriamiento}")
        print(f"Iteraciones máximas: {iteraciones_maximas}")

        if df_aulas is not None:
            print("Movimiento de cambio de aula: ACTIVADO")
        else:
            print("Movimiento de cambio de aula: DESACTIVADO")

    # -----------------------------------------------------
    # BUCLE PRINCIPAL
    # -----------------------------------------------------

    while (
        iteraciones < iteraciones_maximas
        and temperatura > temperatura_final
    ):

        iteraciones += 1

        # Generar un horario vecino.
        solucion_nueva = generar_vecino(
            solucion_actual,
            horas_por_dia=horas_por_dia,
            generador=generador,
            df_aulas=df_aulas
        )

        if solucion_nueva is None:

            movimientos_fallidos += 1

        else:

            coste_nuevo = calcular_coste(
                solucion_nueva,
                horas_por_dia
            )

            if aceptar_solucion(
                coste_actual,
                coste_nuevo,
                temperatura,
                generador
            ):

                if coste_nuevo > coste_actual:
                    soluciones_peores_aceptadas += 1

                solucion_actual = solucion_nueva
                coste_actual = coste_nuevo

                aceptados += 1

                # Actualizar la mejor solución global.
                if coste_actual < mejor_coste:

                    mejor_solucion = solucion_actual.copy(
                        deep=True
                    )

                    mejor_coste = coste_actual
                    mejoras += 1

        # Guardar información para analizar la evolución.
        historial.append({
            "iteracion": iteraciones,
            "temperatura": temperatura,
            "coste_actual": coste_actual,
            "mejor_coste": mejor_coste,
        })

        temperatura *= factor_enfriamiento

        if mostrar_progreso and iteraciones % 100 == 0:

            print(
                f"Iteración {iteraciones}: "
                f"coste actual = {coste_actual}, "
                f"mejor coste = {mejor_coste}, "
                f"temperatura = {temperatura:.4f}"
            )

    # -----------------------------------------------------
    # RESULTADOS FINALES
    # -----------------------------------------------------

    tiempo_total = time.perf_counter() - tiempo_inicio

    valido, errores = comprobar_restricciones(
        mejor_solucion,
        horas_por_dia
    )

    if not valido:
        raise RuntimeError(
            "La mejor solución obtenida no es válida:\n"
            + "\n".join(errores[:10])
        )

    if mejor_coste > coste_inicial:
        raise RuntimeError(
            "Error: la mejor solución es peor que la inicial."
        )

    if mostrar_progreso:

        print("\n" + "=" * 60)
        print("RECOCIDO SIMULADO FINALIZADO")
        print("=" * 60)

        print(f"Coste inicial: {coste_inicial}")
        print(f"Mejor coste: {mejor_coste}")
        print(f"Iteraciones realizadas: {iteraciones}")
        print(f"Movimientos aceptados: {aceptados}")
        print(f"Mejoras encontradas: {mejoras}")

        print(
            "Soluciones peores aceptadas: "
            f"{soluciones_peores_aceptadas}"
        )

        print(f"Movimientos fallidos: {movimientos_fallidos}")
        print(f"Tiempo total: {tiempo_total:.3f} segundos")
        print(f"Horario válido: {valido}")

    return {
        "horario": mejor_solucion,
        "coste_inicial": coste_inicial,
        "mejor_coste": mejor_coste,
        "iteraciones": iteraciones,
        "aceptados": aceptados,
        "mejoras": mejoras,
        "soluciones_peores_aceptadas": soluciones_peores_aceptadas,
        "movimientos_fallidos": movimientos_fallidos,
        "tiempo": tiempo_total,
        "valido": valido,
        "errores": errores,
        "historial": historial,
    }

